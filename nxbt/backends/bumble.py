import asyncio
import logging
import socket
import threading
import xml.etree.ElementTree as ET

from bumble.core import UUID
from bumble.device import Device
from bumble.hci import HCI_Write_Default_Link_Policy_Settings_Command
from bumble.keys import JsonKeyStore
from bumble.l2cap import ClassicChannel, ClassicChannelSpec
from bumble.pairing import PairingConfig, PairingDelegate
from bumble.sdp import DataElement, ServiceAttribute
from bumble.transport import open_transport

from .internal.bluez import get_hci_state, toggle_hci_adapter

from ..controller.controller import ControllerTypes
from ..utils import load_file
from .base import Backend

HID_CONTROL_PSM = 0x0011
HID_INTERRUPT_PSM = 0x0013


class _ChannelSocketBridge:
    """Bridges a Bumble ClassicChannel to a Python socket via a socketpair.

    Two asyncio tasks forward data:
    - _drain: reads server-sent data from socketpair, sends to Bumble channel
    - _pump: drains PDU queue, writes to socketpair end for server to recv
    """

    def __init__(self, channel: ClassicChannel):
        self.channel = channel
        self.loop = asyncio.get_running_loop()
        self._pdu_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._closed = False
        self._channel_open = asyncio.Event()

        if hasattr(socket, "AF_UNIX"):
            s1, self.socket = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        else:
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            s1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s1.settimeout(5)
            s1.connect(listener.getsockname())
            self.socket, _ = listener.accept()
            s1.settimeout(None)
            listener.close()
        self._s1 = s1
        self._s1.setblocking(False)

        def channel_sink(pdu: bytes):
            if not self._closed:
                self.loop.call_soon_threadsafe(self._pdu_queue.put_nowait, pdu)

        channel.sink = channel_sink
        channel.on("close", lambda: self.loop.call_soon_threadsafe(self._shutdown))
        channel.on(
            "open", lambda: self.loop.call_soon_threadsafe(self._channel_open.set)
        )

        # Check if already open
        if getattr(channel, "state", None) == channel.State.OPEN:
            self._channel_open.set()

        self._drain_task = self.loop.create_task(self._drain())
        self._pump_task = self.loop.create_task(self._pump())

    async def _drain(self):
        try:
            # Wait for the channel to be fully open before sending any PDUs
            if not self._channel_open.is_set():
                try:
                    await asyncio.wait_for(self._channel_open.wait(), timeout=30)
                except asyncio.TimeoutError:
                    return
            while not self._closed:
                data = await self.loop.sock_recv(self._s1, 4096)
                if not data:
                    break
                if self._closed:
                    break
                if not self._channel_open.is_set():
                    continue
                self.channel.send_pdu(data)
        except OSError:
            pass
        finally:
            self._shutdown()

    async def _pump(self):
        try:
            while not self._closed:
                pdu = await self._pdu_queue.get()
                if pdu is None:
                    break
                try:
                    await self.loop.sock_sendall(self._s1, pdu)
                except OSError:
                    break
        except asyncio.CancelledError:
            pass
        finally:
            self._shutdown()

    def _shutdown(self):
        if self._closed:
            return
        self._closed = True
        self._pdu_queue.put_nowait(None)
        for s in (self._s1, self.socket):
            try:
                s.shutdown(socket.SHUT_WR)
            except OSError:
                pass
        self._drain_task.cancel()
        self._pump_task.cancel()
        try:
            self._s1.close()
        except OSError:
            pass

    close = _shutdown


class _BumbleSocket:
    """Wraps a socket with getpeername/getsockname returning Bluetooth addresses."""

    def __init__(self, sock: socket.socket, peer_address: str, local_address: str):
        self._sock = sock
        self._peer_address = peer_address
        self._local_address = local_address

    def recv(self, bufsize: int, flags: int = 0) -> bytes:
        return self._sock.recv(bufsize, flags)

    def send(self, data: bytes, flags: int = 0) -> int:
        return self._sock.send(data, flags)

    def sendall(self, data: bytes, flags: int = 0) -> None:
        self._sock.sendall(data, flags)

    def getpeername(self):
        return (self._peer_address,)

    def getsockname(self):
        return (self._local_address,)

    def fileno(self):
        return self._sock.fileno()

    def setblocking(self, flag: bool):
        self._sock.setblocking(flag)

    def settimeout(self, value):
        self._sock.settimeout(value)

    def gettimeout(self):
        return self._sock.gettimeout()

    def close(self):
        self._sock.close()

    def shutdown(self, how):
        self._sock.shutdown(how)


class BumbleBackend(Backend):
    """Bumble Bluetooth stack backend implementation."""

    ALIASES = {
        ControllerTypes.JOYCON_L: "Joy-Con (L)",
        ControllerTypes.JOYCON_R: "Joy-Con (R)",
        ControllerTypes.PRO_CONTROLLER: "Pro Controller",
    }

    @staticmethod
    def get_available_adapters() -> list[str]:
        """Scan for HCI adapters via HCI sockets or USB."""
        adapters = []

        import glob
        import os
        import platform

        if platform.system() == "Linux":
            for entry in os.listdir("/sys/class/bluetooth/"):
                if not entry.startswith("hci"):
                    continue
                idx = entry.replace("hci", "")
                # Check rfkill state — adapter must not be soft or hard blocked
                blocked = False
                for rfkill_state in glob.glob(
                    f"/sys/class/bluetooth/{entry}/rfkill*/state"
                ):
                    try:
                        with open(rfkill_state) as f:
                            if f.read().strip() == "0":
                                blocked = True
                                break
                    except OSError:
                        pass
                if not blocked:
                    adapters.append(f"hci-socket:{idx}")

        # Scan for USB Bluetooth adapters as fallback
        try:
            import usb.core

            # Use libusb_package if available (required on Windows)
            try:
                import libusb_package

                usb_find = libusb_package.find
            except ImportError:
                usb_find = usb.core.find

            BT_HCI_CLASS = (0xE0, 0x01, 0x01)  # Wireless Controller / RF / Bluetooth
            bt_count = 0

            for dev in usb_find(find_all=True):
                is_hci = (
                    dev.bDeviceClass,
                    dev.bDeviceSubClass,
                    dev.bDeviceProtocol,
                ) == BT_HCI_CLASS
                if not is_hci and dev.bDeviceClass == 0x00:
                    for cfg in dev:
                        for intf in cfg:
                            if (
                                intf.bInterfaceClass,
                                intf.bInterfaceSubClass,
                                intf.bInterfaceProtocol,
                            ) == BT_HCI_CLASS:
                                is_hci = True
                                break
                        if is_hci:
                            break
                if is_hci:
                    adapters.append(f"usb:{bt_count}")
                    bt_count += 1
        except Exception:
            pass
        return adapters

    @staticmethod
    def get_switch_addresses() -> list[str]:
        addresses = []
        try:
            for path in JsonKeyStore().directory_name.iterdir():
                keystore = JsonKeyStore(None, str(path))
                entries = asyncio.run(keystore.get_all())
                addresses += [entry[0].replace("/P", "") for entry in entries]
        except FileNotFoundError:
            pass
        return addresses

    def __init__(
        self,
        adapter_idx: str | None = None,
    ):
        super().__init__(adapter_idx)
        self.logger = logging.getLogger("nxbt")

        # Default to first available HCI socket adapter
        if adapter_idx is None:
            adapters = self.get_available_adapters()
            adapter_idx = adapters[0] if adapters else "hci-socket:0"

        self._transport_spec = adapter_idx
        self._transport_idx = int(self._transport_spec.split(":")[1])
        self._device: Device | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._bridges: list[_ChannelSocketBridge] = []
        # For accept() coordination
        self._ctrl_future: asyncio.Future | None = None
        self._itr_future: asyncio.Future | None = None
        self._transport = None
        # Store controller type for device reset
        self._pending_controller_type = None
        # Save old hci state to restore
        self._hci_old_state = None

    @property
    def address(self) -> str:
        if self._device is not None:
            addr = self._device.public_address or self._device.random_address
            return str(addr).upper()
        return "00:00:00:00:00:00"

    def _start_event_loop(self):
        """Start a persistent asyncio event loop in a background thread."""
        self._loop = asyncio.new_event_loop()

        def run_loop():
            asyncio.set_event_loop(self._loop)
            self._loop.run_forever()

        self._loop_thread = threading.Thread(
            target=run_loop, daemon=True, name="nxbt-bumble-loop"
        )
        self._loop_thread.start()

    def _stop_event_loop(self):
        for bridge in self._bridges:
            bridge.close()
        self._bridges.clear()

        if self._transport:
            try:
                self._run_async(self._transport.close())
            except Exception:
                pass
            self._transport = None

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2)
        if self._loop:
            try:
                self._loop.close()
            except Exception:
                pass
        self._loop = None
        self._device = None

    def _reattach_usb_drivers(self):
        """Reattach kernel drivers on USB interfaces we claimed."""
        if not self._transport_spec.startswith("usb:"):
            return
        try:
            import usb.core

            try:
                import libusb_package

                usb_find = libusb_package.find
            except ImportError:
                usb_find = usb.core.find

            try:
                usb_idx = int(self._transport_spec.split(":")[1])
                devices = list(
                    usb_find(
                        find_all=True,
                        bDeviceClass=0xE0,
                        bDeviceSubClass=0x01,
                        bDeviceProtocol=0x01,
                    )
                )
                self.logger.debug(
                    f"USB cleanup: usb_idx={usb_idx}, devices_found={len(devices)}"
                )
                if usb_idx < len(devices):
                    usb_device = devices[usb_idx]
                else:
                    self.logger.debug("No matching USB device found for cleanup")
                    return
            except Exception as e:
                self.logger.debug(f"USB device lookup failed: {e}")
                return
            for cfg in usb_device:
                for intf in cfg:
                    if usb_device.is_kernel_driver_active(intf.bInterfaceNumber):
                        continue
                    try:
                        import time

                        time.sleep(0.01)  # Avoid resource busy
                        usb_device.attach_kernel_driver(intf.bInterfaceNumber)
                        self.logger.debug(
                            f"Reattached kernel driver to interface {intf.bInterfaceNumber}"
                        )
                    except Exception as e:
                        pass
            self.logger.debug("USB kernel drivers reattached")
        except Exception as e:
            self.logger.debug(f"Failed to reattach USB kernel drivers: {e}")

    def shutdown(self):
        """Clean up the transport, bridges, and event loop."""
        self._stop_event_loop()
        if self._hci_old_state is not None:
            toggle_hci_adapter(self._transport_idx, not self._hci_old_state)
        if self._transport_spec.startswith("usb"):
            self._reattach_usb_drivers()

    def _run_async(self, coro):
        """Run an async coroutine on the background event loop."""
        assert self._loop is not None
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=30)

    def _xml_to_data_element(self, elem: ET.Element) -> DataElement:
        """Convert an SDP XML element tree to a Bumble DataElement."""
        de = DataElement
        tag = elem.tag
        if tag == "record":
            return de(de.SEQUENCE, [self._xml_to_data_element(child) for child in elem])
        elif tag == "attribute":
            attr_id = int(elem.attrib["id"], 0)
            id_elem = de(de.UNSIGNED_INTEGER, attr_id, value_size=2)
            return de(
                de.SEQUENCE,
                [id_elem] + [self._xml_to_data_element(child) for child in elem],
            )
        elif tag == "sequence":
            return de(de.SEQUENCE, [self._xml_to_data_element(child) for child in elem])
        elif tag == "uuid":
            value = elem.attrib["value"]
            # Convert hex string like "0x1124" to full UUID
            if value.startswith("0x"):
                return de(de.UUID, UUID.from_16_bits(int(value, 16)))
            return de(de.UUID, UUID(value))
        elif tag == "uint8":
            return de(de.UNSIGNED_INTEGER, int(elem.attrib["value"], 0), value_size=1)
        elif tag == "uint16":
            return de(de.UNSIGNED_INTEGER, int(elem.attrib["value"], 0), value_size=2)
        elif tag == "text":
            text_value = elem.attrib["value"]
            if elem.attrib.get("encoding") == "hex":
                return de(de.TEXT_STRING, bytes.fromhex(text_value))
            return de(de.TEXT_STRING, text_value.encode("utf-8"))
        elif tag == "boolean":
            return de(de.BOOLEAN, elem.attrib["value"].lower() == "true")
        else:
            raise ValueError(f"Unknown SDP element: {tag}")

    def _build_sdp_record(self) -> list:
        """Parse the SDP service record from switch-controller.xml."""
        sdp_record_path = load_file("../controller/sdp/switch-controller.xml")
        tree = ET.parse(sdp_record_path)
        root = tree.getroot()
        record = self._xml_to_data_element(root)
        # Record is a SEQUENCE of ATTRIBUTE elements; extract into attribute list
        assert record.type == DataElement.SEQUENCE
        service_attributes = []
        for attr_elem in record.value:
            if attr_elem.type != DataElement.SEQUENCE or len(attr_elem.value) != 2:
                continue
            attr_id = attr_elem.value[0]
            attr_value = attr_elem.value[1]
            if attr_id.type == DataElement.UNSIGNED_INTEGER:
                service_attributes.append(ServiceAttribute(attr_id.value, attr_value))
        return service_attributes

    def _patch_intel_driver_variant(self):
        """Make hardware variant 0x18 compare equal to the allowed variants so the hardcoded check passes."""
        try:
            from bumble.drivers import intel as intel_drv

            if getattr(intel_drv.HardwareVariant.__eq__, "_nxbt_patched", False):
                return
            _orig_eq = intel_drv.HardwareVariant.__eq__

            def _patched_eq(self, other):
                if other.value == 0x18:
                    return True
                return _orig_eq(self, other)

            _patched_eq._nxbt_patched = True
            intel_drv.HardwareVariant.__eq__ = _patched_eq
        except Exception as e:
            self.logger.debug(f"Intel driver patch skipped: {e}")

    def _setup_async(self, controller_type):
        """Async setup of the Bumble device."""
        self._patch_intel_driver_variant()
        if self._transport_spec.startswith("hci"):
            self._hci_old_state = get_hci_state(self._transport_idx)
            if self._hci_old_state:
                toggle_hci_adapter(self._transport_idx)

        # Open transport
        self._transport = self._run_async(open_transport(self._transport_spec))

        # Create device — use the HCI adapter's real public address
        self._device = Device.with_hci(
            self.ALIASES[controller_type],
            None,
            self._transport.source,
            self._transport.sink,
        )

        # Configure Classic Bluetooth
        self._device.config.keystore = "JsonKeyStore"
        self._device.classic_enabled = True
        self._device.class_of_device = 0x002508  # Gamepad
        self._device.discoverable = True
        self._device.connectable = True

        # Configure pairing (NoInputNoOutput, auto-accept)
        self._device.pairing_config_factory = lambda _: PairingConfig(
            sc=True,
            mitm=False,
            bonding=True,
            delegate=PairingDelegate(
                io_capability=PairingDelegate.IoCapability.NO_OUTPUT_NO_INPUT
            ),
        )

        # Register SDP service record
        sdp_record = self._build_sdp_record()
        self.logger.debug(f"SDP record registered: {len(sdp_record)} attributes")
        self._device.sdp_service_records = {0x00010001: sdp_record}
        # Power on
        self._run_async(self._device.power_on())
        # Write default link policy
        self._run_async(
            self._device.send_command(
                HCI_Write_Default_Link_Policy_Settings_Command(
                    default_link_policy_settings=0x0005
                )
            )
        )

    def setup(self, controller_type) -> None:
        self._pending_controller_type = controller_type
        self._start_event_loop()
        try:
            self._setup_async(controller_type)
        except Exception:
            self._stop_event_loop()
            # Reattach USB kernel drivers on setup failure so retries can succeed
            self._reattach_usb_drivers()
            raise

    def _on_l2cap_connection(self, psm: int, channel: ClassicChannel):
        """Called when a peer connects to one of our L2CAP servers."""
        if self._device is None:
            return
        local_addr = str(self._device.public_address or self._device.random_address)
        peer_addr = str(channel.connection.peer_address)

        def _on_open():
            self.logger.debug(
                f"[L2CAP PSM={psm}] channel OPEN state reached, "
                f"src_cid={channel.source_cid}, dst_cid={channel.destination_cid}, "
                f"MTU={channel.mtu}/{channel.peer_mtu}"
            )

        def _on_close():
            self.logger.warning(
                f"[L2CAP PSM={psm}] channel CLOSED, state={channel.state.name}, "
                f"src_cid={channel.source_cid}, dst_cid={channel.destination_cid}"
            )

        channel.on("open", _on_open)
        channel.on("close", _on_close)

        bridge = _ChannelSocketBridge(channel)
        self._bridges.append(bridge)

        bumble_socket = _BumbleSocket(bridge.socket, peer_addr, local_addr)
        # Also store the bridge on the socket for cleanup
        bumble_socket._bridge = bridge

        if psm == HID_INTERRUPT_PSM:
            if self._itr_future and not self._itr_future.done():
                self._loop.call_soon_threadsafe(
                    self._itr_future.set_result, bumble_socket
                )
        elif psm == HID_CONTROL_PSM:
            if self._ctrl_future and not self._ctrl_future.done():
                self._loop.call_soon_threadsafe(
                    self._ctrl_future.set_result, bumble_socket
                )

    def accept(self) -> tuple:
        self._bridges = []
        self._ctrl_future = self._loop.create_future()
        self._itr_future = self._loop.create_future()

        # Register L2CAP servers — if PSMs are already registered from a
        # previous failed setup, reset the device and retry.
        try:
            self._device.create_l2cap_server(
                spec=ClassicChannelSpec(psm=HID_CONTROL_PSM),
                handler=lambda ch: self._on_l2cap_connection(HID_CONTROL_PSM, ch),
            )
            self._device.create_l2cap_server(
                spec=ClassicChannelSpec(psm=HID_INTERRUPT_PSM),
                handler=lambda ch: self._on_l2cap_connection(HID_INTERRUPT_PSM, ch),
            )
        except Exception as e:
            self.logger.debug(f"L2CAP server registration failed: {e}")
            raise

        self.logger.debug("BumbleBackend: waiting for incoming HID connections...")

        self._run_async(asyncio.wait_for(self._ctrl_future, 120))
        self._run_async(asyncio.wait_for(self._itr_future, 120))

        ctrl = self._ctrl_future.result()
        itr = self._itr_future.result()

        self.logger.debug(
            f"BumbleBackend: accepted connection from {itr.getpeername()[0]}"
        )
        self._ctrl_future = None
        self._itr_future = None
        return itr, ctrl

    def reconnect(self, reconnect_address: str) -> tuple:
        async def create_bridges(address: str):
            if 256 in self._device.connections:
                conn = self._device.connections[256]
            else:
                conn = await self._device.connect_classic(address)
                await conn.authenticate()
                await conn.encrypt()
            # Old bridges have dead socketpairs (shutdown on channel close).
            # Create fresh L2CAP channels and fresh bridges.
            ctrl_channel = await conn.create_l2cap_channel(
                ClassicChannelSpec(psm=HID_CONTROL_PSM)
            )
            itr_channel = await conn.create_l2cap_channel(
                ClassicChannelSpec(psm=HID_INTERRUPT_PSM)
            )

            # Replace old dead bridges with fresh ones
            itr_bridge = _ChannelSocketBridge(itr_channel)
            ctrl_bridge = _ChannelSocketBridge(ctrl_channel)

            return itr_bridge, ctrl_bridge

        addresses = (
            reconnect_address
            if isinstance(reconnect_address, list)
            else [reconnect_address]
        )

        for address in addresses:
            self.logger.debug(f"BumbleBackend: reconnecting to {address}...")
            local_addr = str(self._device.public_address or self._device.random_address)
            self._bridges.clear()

            itr_bridge, ctrl_bridge = self._run_async(create_bridges(address))

            self._bridges.append(itr_bridge)
            itr = _BumbleSocket(itr_bridge.socket, address, local_addr)
            itr._bridge = itr_bridge

            self._bridges.append(ctrl_bridge)
            ctrl = _BumbleSocket(ctrl_bridge.socket, address, local_addr)
            ctrl._bridge = ctrl_bridge

            self.logger.debug(f"BumbleBackend: reconnected to {address}")
            return itr, ctrl

        raise OSError(
            "Unable to reconnect to channels at the given address(es)",
            reconnect_address,
        )

    def remove_bonded_device(self, address):
        """Remove pairing keys for *address* from the JsonKeyStore file."""

        import json

        dir_path = JsonKeyStore().directory_name
        for file_path in dir_path.iterdir():
            with open(file_path, "r") as f:
                data = json.load(f)
            for namespace in data:
                keystore = JsonKeyStore(namespace, str(file_path))
                try:
                    self._run_async(keystore.delete(address + "/P"))
                    self.logger.debug(
                        f"Removed bonded device {address} from keystore {file_path}"
                    )
                except KeyError:
                    pass

    def __del__(self):
        self._stop_event_loop()
