import logging
import shutil
from pathlib import Path
import socket
import time
from threading import Thread

from .internal.bluez import (
    BlueZ,
    find_objects,
    find_devices_by_alias,
    toggle_clean_bluez,
    SERVICE_NAME,
    ADAPTER_INTERFACE,
)
from ..controller.controller import ControllerTypes
from ..controller.sdp import SWITCH_CONTROLLER_SDP
from .base import Backend


class BlueZBackend(Backend):
    """BlueZ (D-Bus) backend implementation."""

    GAMEPAD_CLASS = "0x002508"
    SDP_UUID = "00001000-0000-1000-8000-00805f9b34fb"
    SDP_RECORD_PATH = "/nxbt/controller"
    ALIASES = {
        ControllerTypes.JOYCON_L: "Joy-Con (L)",
        ControllerTypes.JOYCON_R: "Joy-Con (R)",
        ControllerTypes.PRO_CONTROLLER: "Pro Controller",
    }

    def __init__(self, adapter_idx="/org/bluez/hci0"):
        super().__init__(adapter_idx)
        self.logger = logging.getLogger("nxbt")
        self._bt = BlueZ(adapter_path=adapter_idx)
        self._crw_running = False
        self._crw_thread = None

        # Disable the BlueZ input plugin so we can use the
        # HID control/interrupt Bluetooth ports

        toggle_clean_bluez(True)

    def shutdown(self):
        """Clean up the transport, bridges, and event loop."""

        # Re-enable the BlueZ plugins, if we have permission
        toggle_clean_bluez(False)

    @staticmethod
    def get_available_adapters() -> list:
        return find_objects(SERVICE_NAME, ADAPTER_INTERFACE)

    @staticmethod
    def get_switch_addresses() -> list:
        return find_devices_by_alias("Nintendo Switch")

    @property
    def address(self) -> str:
        return self._bt.address.upper()

    def setup(self, controller_type) -> None:
        self._bt.set_powered(True)
        self._bt.set_pairable(True)
        self._bt.set_pairable_timeout(0)
        self._bt.set_discoverable_timeout(180)
        self._bt.set_alias(self.ALIASES[controller_type])
        # Adding the SDP record
        sdp_record = SWITCH_CONTROLLER_SDP

        opts = {
            "ServiceRecord": sdp_record,
            "Role": "server",
            "RequireAuthentication": False,
            "RequireAuthorization": False,
            "AutoConnect": True,
        }

        try:
            self._bt.register_profile(self.SDP_RECORD_PATH, self.SDP_UUID, opts)
        except Exception as e:
            self.logger.debug(e)

    def accept(self) -> tuple:
        s_ctrl = socket.socket(
            family=socket.AF_BLUETOOTH,
            type=socket.SOCK_SEQPACKET,
            proto=socket.BTPROTO_L2CAP,
        )
        s_itr = socket.socket(
            family=socket.AF_BLUETOOTH,
            type=socket.SOCK_SEQPACKET,
            proto=socket.BTPROTO_L2CAP,
        )

        try:
            s_ctrl.bind((self._bt.address, 17))
            s_itr.bind((self._bt.address, 19))
        except OSError:
            s_ctrl.bind((socket.BDADDR_ANY, 17))
            s_itr.bind((socket.BDADDR_ANY, 19))

        s_itr.listen(1)
        s_ctrl.listen(1)

        self._bt.setup_auto_accept_pairing()
        self._bt.set_discoverable(True)
        self._bt.set_class(self.GAMEPAD_CLASS)

        self._crw_running = True
        self._crw_thread = Thread(
            target=self._connection_reset_watchdog,
            daemon=True,
            name="nxbt-bt-crw",
        )
        self._crw_thread.start()

        itr, _ = s_itr.accept()
        ctrl, _ = s_ctrl.accept()

        self._crw_running = False

        return itr, ctrl

    def reconnect(self, reconnect_address) -> tuple:
        ctrl = socket.socket(
            family=socket.AF_BLUETOOTH,
            type=socket.SOCK_SEQPACKET,
            proto=socket.BTPROTO_L2CAP,
        )
        itr = socket.socket(
            family=socket.AF_BLUETOOTH,
            type=socket.SOCK_SEQPACKET,
            proto=socket.BTPROTO_L2CAP,
        )

        addresses = (
            reconnect_address
            if isinstance(reconnect_address, list)
            else [reconnect_address]
        )

        for address in addresses:
            try:
                ctrl.connect((address, 17))
                itr.connect((address, 19))
                return itr, ctrl
            except OSError:
                pass

        itr.close()
        ctrl.close()
        raise OSError(
            "Unable to reconnect to sockets at the given address(es)",
            reconnect_address,
        )

    @classmethod
    def remove_bonded_device(address):
        bt_dir = Path("/var/lib/bluetooth")
        if not bt_dir.exists():
            return

        # Find adapter dirs
        for adapter_dir in bt_dir.iterdir():
            device_path = adapter_dir / address.upper()
            if device_path.exists():
                shutil.rmtree(device_path)
                logging.getLogger("nxbt").info(f"Removed bonded device {address}")
                break

    def _connection_reset_watchdog(self):
        bonded = set(self._bt.find_bonded_devices_by_alias("Nintendo Switch"))
        if not bonded:
            self.logger.debug("No bonded devices found, watchdog idle")
            return

        connected = set()
        flap_count = {}
        while self._crw_running:
            paths = set(self._bt.find_connected_devices())

            newly_connected = paths - connected
            newly_disconnected = connected - paths

            for path in newly_disconnected:
                if path in bonded:
                    flap_count[path] = flap_count.get(path, 0) + 1
                    if flap_count[path] >= 2:
                        self.logger.debug(
                            "A bonded device flap-detected. Resetting connection..."
                        )
                        self.logger.debug(f"Removing {path}")
                        self._bt.remove_device(path)
                        flap_count[path] = 0

            for path in newly_connected:
                if path in bonded:
                    connected.add(path)
            connected -= newly_disconnected

            time.sleep(0.1)
