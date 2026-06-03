"""
Bluetooth Management (mgmt) Protocol — Python implementation.

Wraps the Linux kernel mgmt interface (HCI_CHANNEL_CONTROL) from BlueZ.
Requires Linux >= 3.4 and CAP_NET_ADMIN.
"""

import enum
import errno
import os
import socket
import struct
import select
from dataclasses import dataclass
from typing import Callable, Optional
import ctypes

# ─── Socket helpers ───────────────────────────────────────────────────────

AF_BLUETOOTH = 31
BTPROTO_HCI = 1
SOL_HCI = 0

HCI_DEV_NONE = 0xFFFF
HCI_CHANNEL_CONTROL = 3

MGMT_HDR_FMT = "<HHH"  # code(2) + index(2) + param_len(2)
MGMT_HDR_SIZE = struct.calcsize(MGMT_HDR_FMT)


def mgmt_create() -> socket.socket:
    """Create and bind a raw HCI mgmt socket. Returns socket object or raises OSError."""
    try:
        sock = socket.socket(
            AF_BLUETOOTH,
            socket.SOCK_RAW | socket.SOCK_CLOEXEC | socket.SOCK_NONBLOCK,
            BTPROTO_HCI,
        )
    except OSError as e:
        err = e.errno or errno.EIO
        print(
            f"mgmt_create: socket() failed with errno={err} ({errno.errorcode.get(err, '?')})"
        )
        raise

    try:
        # Bind using ctypes to handle the sockaddr_hci structure
        ctypes.cdll.LoadLibrary("libc.so.6")
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
    except OSError as error:
        sock.close()
        raise Exception(
            "Bluetooth HCI sockets not supported on this platform"
        ) from error

    libc.bind.argtypes = (ctypes.c_int, ctypes.POINTER(ctypes.c_char), ctypes.c_int)
    libc.bind.restype = ctypes.c_int

    # sockaddr_hci { family(2) dev(2) channel(2) } packed as "<HHH"
    addr = struct.pack("<HHH", AF_BLUETOOTH, HCI_DEV_NONE, HCI_CHANNEL_CONTROL)

    if (
        libc.bind(
            sock.fileno(),
            ctypes.create_string_buffer(addr),
            len(addr),
        )
        != 0
    ):
        err = ctypes.get_errno()
        sock.close()
        raise OSError(err, os.strerror(err))

    return sock


# ─── Address Types ────────────────────────────────────────────────────────


class AddrType(enum.IntEnum):
    BR_EDR = 0x00
    LE_PUBLIC = 0x01
    LE_RANDOM = 0x02


# ─── Error Codes ──────────────────────────────────────────────────────────


class ErrorCode(enum.IntEnum):
    SUCCESS = 0x00
    UNKNOWN_COMMAND = 0x01
    NOT_CONNECTED = 0x02
    FAILED = 0x03
    CONNECT_FAILED = 0x04
    AUTH_FAILED = 0x05
    NOT_PAIRED = 0x06
    NO_RESOURCES = 0x07
    TIMEOUT = 0x08
    ALREADY_CONNECTED = 0x09
    BUSY = 0x0A
    REJECTED = 0x0B
    NOT_SUPPORTED = 0x0C
    INVALID_PARAMETERS = 0x0D
    DISCONNECTED = 0x0E
    NOT_POWERED = 0x0F
    CANCELLED = 0x10
    INVALID_INDEX = 0x11
    RFKILLED = 0x12
    ALREADY_PAIRED = 0x13
    PERMISSION_DENIED = 0x14


# ─── Settings Bitmask ─────────────────────────────────────────────────────


class Setting(enum.IntFlag):
    POWERED = 1 << 0
    CONNECTABLE = 1 << 1
    FAST_CONNECTABLE = 1 << 2
    DISCOVERABLE = 1 << 3
    BONDABLE = 1 << 4
    LINK_SECURITY = 1 << 5
    SECURE_SIMPLE_PAIRING = 1 << 6
    BR_EDR = 1 << 7
    HIGH_SPEED = 1 << 8
    LOW_ENERGY = 1 << 9
    ADVERTISING = 1 << 10
    SECURE_CONNECTIONS = 1 << 11
    DEBUG_KEYS = 1 << 12
    PRIVACY = 1 << 13
    CONTROLLER_CONFIG = 1 << 14
    STATIC_ADDRESS = 1 << 15
    PHY_CONFIG = 1 << 16
    WIDEBAND_SPEECH = 1 << 17
    CIS_CENTRAL = 1 << 18
    CIS_PERIPHERAL = 1 << 19
    ISO_BROADCASTER = 1 << 20
    SYNC_RECEIVER = 1 << 21
    LL_PRIVACY = 1 << 22


# ─── Command Codes ────────────────────────────────────────────────────────


class Cmd(enum.IntEnum):
    READ_VERSION_INFORMATION = 0x0001
    READ_SUPPORTED_COMMANDS = 0x0002
    READ_CONTROLLER_INDEX_LIST = 0x0003
    READ_CONTROLLER_INFORMATION = 0x0004
    SET_POWERED = 0x0005
    SET_DISCOVERABLE = 0x0006
    SET_CONNECTABLE = 0x0007
    SET_FAST_CONNECTABLE = 0x0008
    SET_BONDABLE = 0x0009
    SET_LINK_SECURITY = 0x000A
    SET_SECURE_SIMPLE_PAIRING = 0x000B
    SET_HIGH_SPEED = 0x000C
    SET_LOW_ENERGY = 0x000D
    SET_DEVICE_CLASS = 0x000E
    SET_LOCAL_NAME = 0x000F
    ADD_UUID = 0x0010
    REMOVE_UUID = 0x0011
    LOAD_LINK_KEYS = 0x0012
    LOAD_LONG_TERM_KEYS = 0x0013
    DISCONNECT = 0x0014
    GET_CONNECTIONS = 0x0015
    PIN_CODE_REPLY = 0x0016
    PIN_CODE_NEGATIVE_REPLY = 0x0017
    SET_IO_CAPABILITY = 0x0018
    PAIR_DEVICE = 0x0019
    CANCEL_PAIR_DEVICE = 0x001A
    UNPAIR_DEVICE = 0x001B
    USER_CONFIRMATION_REPLY = 0x001C
    USER_CONFIRMATION_NEGATIVE_REPLY = 0x001D
    USER_PASSKEY_REPLY = 0x001E
    USER_PASSKEY_NEGATIVE_REPLY = 0x001F
    READ_LOCAL_OOB_DATA = 0x0020
    ADD_REMOTE_OOB_DATA = 0x0021
    REMOVE_REMOTE_OOB_DATA = 0x0022
    START_DISCOVERY = 0x0023
    STOP_DISCOVERY = 0x0024
    CONFIRM_NAME = 0x0025
    BLOCK_DEVICE = 0x0026
    UNBLOCK_DEVICE = 0x0027
    SET_DEVICE_ID = 0x0028
    SET_ADVERTISING = 0x0029
    SET_BR_EDR = 0x002A
    SET_STATIC_ADDRESS = 0x002B
    SET_SCAN_PARAMETERS = 0x002C
    SET_SECURE_CONNECTIONS = 0x002D
    SET_DEBUG_KEYS = 0x002E
    SET_PRIVACY = 0x002F
    LOAD_IDENTITY_RESOLVING_KEYS = 0x0030
    GET_CONNECTION_INFO = 0x0031
    GET_CLOCK_INFO = 0x0032
    ADD_DEVICE = 0x0033
    REMOVE_DEVICE = 0x0034
    LOAD_CONN_PARAMETERS = 0x0035
    READ_UNCONFIG_INDEX_LIST = 0x0036
    READ_CTRL_CONFIG_INFO = 0x0037
    SET_EXTERNAL_CONFIG = 0x0038
    SET_PUBLIC_ADDRESS = 0x0039
    START_SERVICE_DISCOVERY = 0x003A
    READ_LOCAL_OOB_EXT_DATA = 0x003B
    READ_EXT_CTRL_INDEX_LIST = 0x003C
    READ_ADVERTISING_FEATURES = 0x003D
    ADD_ADVERTISING = 0x003E
    REMOVE_ADVERTISING = 0x003F
    GET_ADV_SIZE_INFO = 0x0040
    START_LIMITED_DISCOVERY = 0x0041
    READ_EXT_CTRL_INFO = 0x0042
    SET_APPEARANCE = 0x0043
    GET_PHY_CONFIGURATION = 0x0044
    SET_PHY_CONFIGURATION = 0x0045
    LOAD_BLOCKED_KEYS = 0x0046
    SET_WIDEBAND_SPEECH = 0x0047
    READ_CTRL_CAPABILITIES = 0x0048
    READ_EXP_FEATURES_INFO = 0x0049
    SET_EXP_FEATURE = 0x004A
    READ_DEFAULT_SYS_CONFIG = 0x004B
    SET_DEFAULT_SYS_CONFIG = 0x004C
    READ_DEFAULT_RUNTIME_CONFIG = 0x004D
    SET_DEFAULT_RUNTIME_CONFIG = 0x004E
    GET_DEVICE_FLAGS = 0x004F
    SET_DEVICE_FLAGS = 0x0050
    READ_ADV_MONITOR_FEATURES = 0x0051
    ADD_ADV_PATTERNS_MONITOR = 0x0052
    REMOVE_ADV_MONITOR = 0x0053
    ADD_EXT_ADV_PARAMETERS = 0x0054
    ADD_EXT_ADV_DATA = 0x0055
    ADD_ADV_PATTERNS_MONITOR_RSSI = 0x0056
    SET_MESH_RECEIVER = 0x0057
    READ_MESH_FEATURES = 0x0058
    TRANSMIT_MESH_PACKET = 0x0059
    CANCEL_TRANSMIT_MESH_PACKET = 0x005A
    SEND_HCI_CMD = 0x005B


# ─── Event Codes ──────────────────────────────────────────────────────────


class Evt(enum.IntEnum):
    COMMAND_COMPLETE = 0x0001
    COMMAND_STATUS = 0x0002
    CONTROLLER_ERROR = 0x0003
    INDEX_ADDED = 0x0004
    INDEX_REMOVED = 0x0005
    NEW_SETTINGS = 0x0006
    CLASS_OF_DEVICE_CHANGED = 0x0007
    LOCAL_NAME_CHANGED = 0x0008
    NEW_LINK_KEY = 0x0009
    NEW_LONG_TERM_KEY = 0x000A
    DEVICE_CONNECTED = 0x000B
    DEVICE_DISCONNECTED = 0x000C
    CONNECT_FAILED = 0x000D
    PIN_CODE_REQUEST = 0x000E
    USER_CONFIRMATION_REQUEST = 0x000F
    USER_PASSKEY_REQUEST = 0x0010
    AUTHENTICATION_FAILED = 0x0011
    DEVICE_FOUND = 0x0012
    DISCOVERING = 0x0013
    DEVICE_BLOCKED = 0x0014
    DEVICE_UNBLOCKED = 0x0015
    DEVICE_UNPAIRED = 0x0016
    PASSKEY_NOTIFY = 0x0017
    NEW_IDENTITY_RESOLVING_KEY = 0x0018
    NEW_SIGNATURE_RESOLVING_KEY = 0x0019
    DEVICE_ADDED = 0x001A
    DEVICE_REMOVED = 0x001B
    NEW_CONN_PARAMETER = 0x001C
    UNCONFIG_INDEX_ADDED = 0x001D
    UNCONFIG_INDEX_REMOVED = 0x001E
    NEW_CONFIG_OPTIONS = 0x001F
    EXT_INDEX_ADDED = 0x0020
    EXT_INDEX_REMOVED = 0x0021
    LOCAL_OOB_EXT_DATA_UPDATED = 0x0022
    ADV_ADDED = 0x0023
    ADV_REMOVED = 0x0024
    EXT_CTRL_INFO_CHANGED = 0x0025
    PHY_CONFIG_CHANGED = 0x0026
    EXP_FEATURE_CHANGED = 0x0027
    DEFAULT_SYS_CONFIG_CHANGED = 0x0028
    DEFAULT_RUNTIME_CONFIG_CHANGED = 0x0029
    DEVICE_FLAGS_CHANGED = 0x002A
    ADV_MONITOR_ADDED = 0x002B
    ADV_MONITOR_REMOVED = 0x002C
    CONTROLLER_SUSPEND = 0x002D
    CONTROLLER_RESUME = 0x002E
    ADV_MONITOR_DEVICE_FOUND = 0x002F
    ADV_MONITOR_DEVICE_LOST = 0x0030
    MESH_DEVICE_FOUND = 0x0031
    MESH_PACKET_TX_COMPLETE = 0x0032


# ─── Packet helpers ───────────────────────────────────────────────────────


def encode_cmd(opcode: int, index: int, params: bytes = b"") -> bytes:
    """Encode a mgmt command frame."""
    return struct.pack(MGMT_HDR_FMT, opcode, index, len(params)) + params


def decode_frame(data: bytes) -> tuple:
    """Decode a mgmt header. Returns (code, index, param_len)."""
    return struct.unpack(MGMT_HDR_FMT, data[:MGMT_HDR_SIZE])


def decode_params(data: bytes, fmt: str) -> tuple:
    """Decode parameters from a mgmt frame payload using a struct format."""
    return struct.unpack(
        fmt, data[MGMT_HDR_SIZE : MGMT_HDR_SIZE + struct.calcsize(fmt)]
    )


# ─── Named tuple-like response helpers ────────────────────────────────────


@dataclass
class CtrlInfo:
    address: str
    bluetooth_version: int
    manufacturer: int
    supported_settings: int
    current_settings: int
    cod: tuple  # (major, minor, service)
    name: str
    short_name: str

    def get_supported_settings(self) -> list[str]:
        return [s.name for s in Setting if self.supported_settings & s]

    def get_current_settings(self) -> list[str]:
        return [s.name for s in Setting if self.current_settings & s]


@dataclass
class VersionInfo:
    version: int
    revision: int


# ─── Client class ─────────────────────────────────────────────────────────


class MgmtClient:
    """High-level wrapper around the mgmt socket."""

    def __init__(self, sock: Optional[socket.socket] = None):
        if sock is None:
            sock = mgmt_create()
        self._sock = sock
        self._handlers: dict[int, Callable] = {}

    @property
    def fd(self) -> int:
        """Return the file descriptor of the underlying socket."""
        return self._sock.fileno()

    @property
    def socket(self) -> socket.socket:
        """Return the underlying socket object."""
        return self._sock

    # ── low-level I/O ─────────────────────────────────────────────────

    def send_cmd(
        self, opcode: int, index: int = HCI_DEV_NONE, params: bytes = b""
    ) -> None:
        """Send a command without waiting for response."""
        self._sock.send(encode_cmd(opcode, index, params))

    def send_cmd_blocking(
        self,
        opcode: int,
        index: int = HCI_DEV_NONE,
        params: bytes = b"",
        timeout: float = 5.0,
    ) -> bytes:
        """Send a command and wait for Command Complete / Command Status.
        Returns the full event payload (without header)."""
        self.send_cmd(opcode, index, params)
        return self._wait_response(opcode, timeout)

    def _wait_response(self, expected_opcode: int, timeout: float) -> bytes:
        """Wait for and process response from mgmt socket."""
        readable, _, _ = select.select([self._sock], [], [], timeout)
        if not readable:
            raise TimeoutError("mgmt response timed out")

        raw = self._sock.recv(65536)
        if not raw:
            raise ConnectionError("mgmt socket closed")

        code, idx, plen = decode_frame(raw)
        payload = raw[MGMT_HDR_SIZE : MGMT_HDR_SIZE + plen]

        if code == Evt.COMMAND_COMPLETE:
            opcode_ret, status = struct.unpack("<HB", payload[:3])
            if opcode_ret != expected_opcode:
                raise ValueError(f"Unexpected response opcode 0x{opcode_ret:04x}")
            if status != ErrorCode.SUCCESS:
                raise RuntimeError(f"mgmt error: {ErrorCode(status).name}")
            return payload[3:]
        elif code == Evt.COMMAND_STATUS:
            opcode_ret, status = struct.unpack("<HB", payload)
            raise RuntimeError(f"mgmt command status: {ErrorCode(status).name}")
        else:
            # Not the expected event; recurse (could queue in real impl)
            return self._wait_response(expected_opcode, timeout)

    # ── event loop ────────────────────────────────────────────────────

    def on_event(self, code: int, handler: Callable) -> None:
        """Register an event handler."""
        self._handlers[code] = handler

    def poll_events(self, timeout: float = 1.0) -> None:
        """Read one pending event and dispatch."""
        readable, _, _ = select.select([self._sock], [], [], timeout)
        if not readable:
            return

        raw = self._sock.recv(65536)
        if not raw:
            return

        code, idx, plen = decode_frame(raw)
        payload = raw[MGMT_HDR_SIZE : MGMT_HDR_SIZE + plen]
        handler = self._handlers.get(code)
        if handler:
            handler(code, idx, payload)

    # ── Commands ──────────────────────────────────────────────────────

    # 0x0001 — Read Management Version Information
    def read_version(self) -> VersionInfo:
        p = self.send_cmd_blocking(Cmd.READ_VERSION_INFORMATION)
        ver, rev = struct.unpack("<BH", p)
        return VersionInfo(ver, rev)

    # 0x0002 — Read Management Supported Commands
    def read_supported_commands(self) -> dict:
        p = self.send_cmd_blocking(Cmd.READ_SUPPORTED_COMMANDS)
        n_cmd, n_evt = struct.unpack("<HH", p[:4])
        cmds = struct.unpack(f"<{n_cmd}H", p[4 : 4 + n_cmd * 2])
        offs = 4 + n_cmd * 2
        evts = struct.unpack(f"<{n_evt}H", p[offs : offs + n_evt * 2])
        return {"commands": cmds, "events": evts}

    # 0x0003 — Read Controller Index List
    def read_controller_index_list(self) -> list[int]:
        p = self.send_cmd_blocking(Cmd.READ_CONTROLLER_INDEX_LIST)
        (n,) = struct.unpack("<H", p[:2])
        return list(struct.unpack(f"<{n}H", p[2 : 2 + n * 2]))

    # 0x0004 — Read Controller Information
    def read_controller_info(self, index: int) -> CtrlInfo:
        p = self.send_cmd_blocking(Cmd.READ_CONTROLLER_INFORMATION, index)
        # address(6) + bt_ver(1) + mfr(2) + sup(4) + cur(4) + cod(3)
        # + name(249) + short_name(11)
        off = 0
        addr = ":".join(f"{b:02X}" for b in reversed(p[off : off + 6]))
        off += 6
        bt_ver = p[off]
        off += 1
        (mfr,) = struct.unpack("<H", p[off : off + 2])
        off += 2
        sup, cur = struct.unpack("<II", p[off : off + 8])
        off += 8
        cod = tuple(p[off : off + 3])
        off += 3
        name = p[off : off + 249].split(b"\x00")[0].decode(errors="replace")
        off += 249
        short_name = p[off : off + 11].split(b"\x00")[0].decode(errors="replace")
        off += 11
        return CtrlInfo(addr, bt_ver, mfr, sup, cur, cod, name, short_name)

    # 0x0005 — Set Powered
    def set_powered(self, index: int, powered: bool) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_POWERED, index, struct.pack("<B", int(powered))
        )
        (cur,) = struct.unpack("<I", p)
        return cur

    # 0x0006 — Set Discoverable
    def set_discoverable(self, index: int, discoverable: int, timeout: int = 0) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_DISCOVERABLE, index, struct.pack("<BH", discoverable, timeout)
        )
        return struct.unpack("<I", p)[0]

    # 0x0007 — Set Connectable
    def set_connectable(self, index: int, connectable: bool) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_CONNECTABLE, index, struct.pack("<B", int(connectable))
        )
        return struct.unpack("<I", p)[0]

    # 0x0008 — Set Fast Connectable
    def set_fast_connectable(self, index: int, enable: bool) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_FAST_CONNECTABLE, index, struct.pack("<B", int(enable))
        )
        return struct.unpack("<I", p)[0]

    # 0x0009 — Set Bondable
    def set_bondable(self, index: int, bondable: bool) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_BONDABLE, index, struct.pack("<B", int(bondable))
        )
        return struct.unpack("<I", p)[0]

    # 0x000A — Set Link Security
    def set_link_security(self, index: int, enabled: bool) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_LINK_SECURITY, index, struct.pack("<B", int(enabled))
        )
        return struct.unpack("<I", p)[0]

    # 0x000B — Set Secure Simple Pairing
    def set_secure_simple_pairing(self, index: int, enabled: bool) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_SECURE_SIMPLE_PAIRING, index, struct.pack("<B", int(enabled))
        )
        return struct.unpack("<I", p)[0]

    # 0x000C — Set High Speed
    def set_high_speed(self, index: int, enabled: bool) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_HIGH_SPEED, index, struct.pack("<B", int(enabled))
        )
        return struct.unpack("<I", p)[0]

    # 0x000D — Set Low Energy
    def set_low_energy(self, index: int, enabled: bool) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_LOW_ENERGY, index, struct.pack("<B", int(enabled))
        )
        return struct.unpack("<I", p)[0]

    # 0x000E — Set Device Class
    def set_device_class(self, index: int, major: int, minor: int) -> bytes:
        p = self.send_cmd_blocking(
            Cmd.SET_DEVICE_CLASS, index, struct.pack("<BB", major, minor)
        )
        return p[:3]

    # 0x000F — Set Local Name
    def set_local_name(
        self, index: int, name: str, short_name: str = ""
    ) -> tuple[str, str]:
        name_b = name.encode()[:248] + b"\x00"
        short_b = short_name.encode()[:10] + b"\x00"
        # pad to exact sizes
        name_b = name_b.ljust(249, b"\x00")
        short_b = short_b.ljust(11, b"\x00")
        p = self.send_cmd_blocking(Cmd.SET_LOCAL_NAME, index, name_b + short_b)
        n = p[:249].split(b"\x00")[0].decode(errors="replace")
        sn = p[249:260].split(b"\x00")[0].decode(errors="replace")
        return n, sn

    # 0x0010 — Add UUID
    def add_uuid(self, index: int, uuid: bytes, svc_hint: bool) -> bytes:
        if len(uuid) != 16:
            raise ValueError("UUID must be 16 bytes")
        p = self.send_cmd_blocking(
            Cmd.ADD_UUID, index, uuid + struct.pack("<B", int(svc_hint))
        )
        return p[:3]

    # 0x0011 — Remove UUID
    def remove_uuid(self, index: int, uuid: bytes) -> bytes:
        if len(uuid) != 16:
            raise ValueError("UUID must be 16 bytes")
        p = self.send_cmd_blocking(Cmd.REMOVE_UUID, index, uuid)
        return p[:3]

    # 0x0012 — Load Link Keys
    def load_link_keys(
        self,
        index: int,
        debug_keys: bool,
        keys: list[tuple[bytes, int, int, bytes, int]],
    ) -> None:
        """keys: list of (addr(6), addr_type, key_type, value(16), pin_len)"""
        buf = struct.pack("<BH", int(debug_keys), len(keys))
        for addr, at, kt, val, pl in keys:
            buf += addr + struct.pack("<BB", at, kt) + val + struct.pack("<B", pl)
        self.send_cmd_blocking(Cmd.LOAD_LINK_KEYS, index, buf)

    # 0x0013 — Load Long Term Keys
    def load_long_term_keys(
        self,
        index: int,
        keys: list[tuple[bytes, int, int, int, int, bytes, bytes, bytes]],
    ) -> None:
        """keys: (addr(6), addr_type, key_type, central, enc_size,
        enc_div(2), rand_num(8), value(16))"""
        buf = struct.pack("<H", len(keys))
        for addr, at, kt, cen, es, ed, rn, val in keys:
            buf += addr + struct.pack("<BBB", at, kt, cen)
            buf += struct.pack("<B", es) + ed + rn + val
        self.send_cmd_blocking(Cmd.LOAD_LONG_TERM_KEYS, index, buf)

    # 0x0014 — Disconnect
    def disconnect(self, index: int, addr: bytes, addr_type: int) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.DISCONNECT, index, addr + struct.pack("<B", addr_type)
        )
        return p[:6], p[6]

    # 0x0015 — Get Connections
    def get_connections(self, index: int) -> list[tuple[bytes, int]]:
        p = self.send_cmd_blocking(Cmd.GET_CONNECTIONS, index)
        (n,) = struct.unpack("<H", p[:2])
        conns = []
        for i in range(n):
            off = 2 + i * 7
            conns.append((p[off : off + 6], p[off + 6]))
        return conns

    # 0x0016 — PIN Code Reply
    def pin_code_reply(
        self, index: int, addr: bytes, addr_type: int, pin: bytes
    ) -> tuple[bytes, int]:
        buf = addr + struct.pack("<BB", addr_type, len(pin))
        buf += pin.ljust(16, b"\x00")
        p = self.send_cmd_blocking(Cmd.PIN_CODE_REPLY, index, buf)
        return p[:6], p[6]

    # 0x0017 — PIN Code Negative Reply
    def pin_code_negative_reply(
        self, index: int, addr: bytes, addr_type: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.PIN_CODE_NEGATIVE_REPLY, index, addr + struct.pack("<B", addr_type)
        )
        return p[:6], p[6]

    # 0x0018 — Set IO Capability
    def set_io_capability(self, index: int, io_cap: int) -> None:
        self.send_cmd_blocking(Cmd.SET_IO_CAPABILITY, index, struct.pack("<B", io_cap))

    # 0x0019 — Pair Device
    def pair_device(
        self, index: int, addr: bytes, addr_type: int, io_cap: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.PAIR_DEVICE, index, addr + struct.pack("<BB", addr_type, io_cap)
        )
        return p[:6], p[6]

    # 0x001A — Cancel Pair Device
    def cancel_pair_device(
        self, index: int, addr: bytes, addr_type: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.CANCEL_PAIR_DEVICE, index, addr + struct.pack("<B", addr_type)
        )
        return p[:6], p[6]

    # 0x001B — Unpair Device
    def unpair_device(
        self, index: int, addr: bytes, addr_type: int, disconnect: bool = True
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.UNPAIR_DEVICE,
            index,
            addr + struct.pack("<BB", addr_type, int(disconnect)),
        )
        return p[:6], p[6]

    # 0x001C — User Confirmation Reply
    def user_confirmation_reply(
        self, index: int, addr: bytes, addr_type: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.USER_CONFIRMATION_REPLY, index, addr + struct.pack("<B", addr_type)
        )
        return p[:6], p[6]

    # 0x001D — User Confirmation Negative Reply
    def user_confirmation_negative_reply(
        self, index: int, addr: bytes, addr_type: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.USER_CONFIRMATION_NEGATIVE_REPLY,
            index,
            addr + struct.pack("<B", addr_type),
        )
        return p[:6], p[6]

    # 0x001E — User Passkey Reply
    def user_passkey_reply(
        self, index: int, addr: bytes, addr_type: int, passkey: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.USER_PASSKEY_REPLY, index, addr + struct.pack("<BI", addr_type, passkey)
        )
        return p[:6], p[6]

    # 0x001F — User Passkey Negative Reply
    def user_passkey_negative_reply(
        self, index: int, addr: bytes, addr_type: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.USER_PASSKEY_NEGATIVE_REPLY, index, addr + struct.pack("<B", addr_type)
        )
        return p[:6], p[6]

    # 0x0020 — Read Local Out Of Band Data
    def read_local_oob_data(self, index: int) -> dict:
        p = self.send_cmd_blocking(Cmd.READ_LOCAL_OOB_DATA, index)
        result = {
            "hash_192": p[:16],
            "randomizer_192": p[16:32],
        }
        if len(p) >= 64:
            result["hash_256"] = p[32:48]
            result["randomizer_256"] = p[48:64]
        return result

    # 0x0021 — Add Remote OOB Data
    def add_remote_oob_data(
        self,
        index: int,
        addr: bytes,
        addr_type: int,
        hash_192: bytes,
        randomizer_192: bytes,
        hash_256: bytes = b"\x00" * 16,
        randomizer_256: bytes = b"\x00" * 16,
    ) -> tuple[bytes, int]:
        buf = addr + struct.pack("<B", addr_type)
        buf += hash_192 + randomizer_192 + hash_256 + randomizer_256
        p = self.send_cmd_blocking(Cmd.ADD_REMOTE_OOB_DATA, index, buf)
        return p[:6], p[6]

    # 0x0022 — Remove Remote OOB Data
    def remove_remote_oob_data(
        self, index: int, addr: bytes, addr_type: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.REMOVE_REMOTE_OOB_DATA, index, addr + struct.pack("<B", addr_type)
        )
        return p[:6], p[6]

    # 0x0023 — Start Discovery
    def start_discovery(self, index: int, addr_type: int) -> int:
        p = self.send_cmd_blocking(
            Cmd.START_DISCOVERY, index, struct.pack("<B", addr_type)
        )
        return p[0]

    # 0x0024 — Stop Discovery
    def stop_discovery(self, index: int, addr_type: int) -> int:
        p = self.send_cmd_blocking(
            Cmd.STOP_DISCOVERY, index, struct.pack("<B", addr_type)
        )
        return p[0]

    # 0x0025 — Confirm Name
    def confirm_name(
        self, index: int, addr: bytes, addr_type: int, name_known: bool
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.CONFIRM_NAME,
            index,
            addr + struct.pack("<BB", addr_type, int(name_known)),
        )
        return p[:6], p[6]

    # 0x0026 — Block Device
    def block_device(
        self, index: int, addr: bytes, addr_type: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.BLOCK_DEVICE, index, addr + struct.pack("<B", addr_type)
        )
        return p[:6], p[6]

    # 0x0027 — Unblock Device
    def unblock_device(
        self, index: int, addr: bytes, addr_type: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.UNBLOCK_DEVICE, index, addr + struct.pack("<B", addr_type)
        )
        return p[:6], p[6]

    # 0x0028 — Set Device ID
    def set_device_id(
        self, index: int, source: int, vendor: int, product: int, version: int
    ) -> None:
        self.send_cmd_blocking(
            Cmd.SET_DEVICE_ID,
            index,
            struct.pack("<HHHH", source, vendor, product, version),
        )

    # 0x0029 — Set Advertising
    def set_advertising(self, index: int, mode: int) -> int:
        """mode: 0=disable, 1=enable, 2=connectable."""
        p = self.send_cmd_blocking(Cmd.SET_ADVERTISING, index, struct.pack("<B", mode))
        return struct.unpack("<I", p)[0]

    # 0x002A — Set BR/EDR
    def set_br_edr(self, index: int, enabled: bool) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_BR_EDR, index, struct.pack("<B", int(enabled))
        )
        return struct.unpack("<I", p)[0]

    # 0x002B — Set Static Address
    def set_static_address(self, index: int, addr: bytes) -> int:
        if len(addr) != 6:
            raise ValueError("Address must be 6 bytes")
        p = self.send_cmd_blocking(Cmd.SET_STATIC_ADDRESS, index, addr)
        return struct.unpack("<I", p)[0]

    # 0x002C — Set Scan Parameters
    def set_scan_parameters(self, index: int, interval: int, window: int) -> None:
        self.send_cmd_blocking(
            Cmd.SET_SCAN_PARAMETERS, index, struct.pack("<HH", interval, window)
        )

    # 0x002D — Set Secure Connections
    def set_secure_connections(self, index: int, mode: int) -> int:
        """0=disabled, 1=enabled, 2=SC only."""
        p = self.send_cmd_blocking(
            Cmd.SET_SECURE_CONNECTIONS, index, struct.pack("<B", mode)
        )
        return struct.unpack("<I", p)[0]

    # 0x002E — Set Debug Keys
    def set_debug_keys(self, index: int, mode: int) -> int:
        """0=discard on disconnect, 1=discard on reboot, 2=SSP debug mode."""
        p = self.send_cmd_blocking(Cmd.SET_DEBUG_KEYS, index, struct.pack("<B", mode))
        return struct.unpack("<I", p)[0]

    # 0x002F — Set Privacy
    def set_privacy(self, index: int, privacy: int, irk: bytes) -> int:
        if len(irk) != 16:
            raise ValueError("IRK must be 16 bytes")
        p = self.send_cmd_blocking(
            Cmd.SET_PRIVACY, index, struct.pack("<B", privacy) + irk
        )
        return struct.unpack("<I", p)[0]

    # 0x0030 — Load Identity Resolving Keys
    def load_identity_resolving_keys(
        self, index: int, keys: list[tuple[bytes, int, bytes]]
    ) -> None:
        """keys: (addr(6), addr_type, value(16))."""
        buf = struct.pack("<H", len(keys))
        for addr, at, val in keys:
            buf += addr + struct.pack("<B", at) + val
        self.send_cmd_blocking(Cmd.LOAD_IDENTITY_RESOLVING_KEYS, index, buf)

    # 0x0031 — Get Connection Information
    def get_connection_info(self, index: int, addr: bytes, addr_type: int) -> dict:
        p = self.send_cmd_blocking(
            Cmd.GET_CONNECTION_INFO, index, addr + struct.pack("<B", addr_type)
        )
        return {
            "rssi": p[7],
            "tx_power": p[8],
            "max_tx_power": p[9],
        }

    # 0x0032 — Get Clock Information
    def get_clock_info(self, index: int, addr: bytes, addr_type: int) -> dict:
        p = self.send_cmd_blocking(
            Cmd.GET_CLOCK_INFO, index, addr + struct.pack("<B", addr_type)
        )
        local_clk, piconet_clk, accuracy = struct.unpack("<IIH", p[7:])
        return {
            "local_clock": local_clk,
            "piconet_clock": piconet_clk,
            "accuracy": accuracy,
        }

    # 0x0033 — Add Device
    def add_device(
        self, index: int, addr: bytes, addr_type: int, action: int
    ) -> tuple[bytes, int]:
        """action: 0=bg scan, 1=allow incoming, 2=auto-connect."""
        p = self.send_cmd_blocking(
            Cmd.ADD_DEVICE, index, addr + struct.pack("<BB", addr_type, action)
        )
        return p[:6], p[6]

    # 0x0034 — Remove Device
    def remove_device(
        self, index: int, addr: bytes, addr_type: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.REMOVE_DEVICE, index, addr + struct.pack("<B", addr_type)
        )
        return p[:6], p[6]

    # 0x0035 — Load Connection Parameters
    def load_conn_parameters(
        self, index: int, params: list[tuple[bytes, int, int, int, int, int]]
    ) -> None:
        """params: (addr, addr_type, min_interval, max_interval,
        latency, supervision_timeout)."""
        buf = struct.pack("<H", len(params))
        for addr, at, mi, ma, lat, to in params:
            buf += addr + struct.pack("<BHHHH", at, mi, ma, lat, to)
        self.send_cmd_blocking(Cmd.LOAD_CONN_PARAMETERS, index, buf)

    # 0x0036 — Read Unconfigured Controller Index List
    def read_unconfig_index_list(self) -> list[int]:
        p = self.send_cmd_blocking(Cmd.READ_UNCONFIG_INDEX_LIST)
        (n,) = struct.unpack("<H", p[:2])
        return list(struct.unpack(f"<{n}H", p[2 : 2 + n * 2]))

    # 0x0037 — Read Controller Configuration Information
    def read_ctrl_config_info(self, index: int) -> dict:
        p = self.send_cmd_blocking(Cmd.READ_CTRL_CONFIG_INFO, index)
        mfr, sup, miss = struct.unpack("<HII", p[:10])
        return {"manufacturer": mfr, "supported_options": sup, "missing_options": miss}

    # 0x0038 — Set External Configuration
    def set_external_config(self, index: int, config: int) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_EXTERNAL_CONFIG, index, struct.pack("<B", config)
        )
        return struct.unpack("<I", p)[0]

    # 0x0039 — Set Public Address
    def set_public_address(self, index: int, addr: bytes) -> int:
        p = self.send_cmd_blocking(Cmd.SET_PUBLIC_ADDRESS, index, addr)
        return struct.unpack("<I", p)[0]

    # 0x003A — Start Service Discovery
    def start_service_discovery(
        self, index: int, addr_type: int, rssi_threshold: int, uuids: list[bytes]
    ) -> int:
        buf = struct.pack("<BBH", addr_type, rssi_threshold, len(uuids))
        for u in uuids:
            buf += u
        p = self.send_cmd_blocking(Cmd.START_SERVICE_DISCOVERY, index, buf)
        return p[0]

    # 0x003B — Read Local Out Of Band Extended Data
    def read_local_oob_ext_data(self, index: int, addr_type: int) -> bytes:
        p = self.send_cmd_blocking(
            Cmd.READ_LOCAL_OOB_EXT_DATA, index, struct.pack("<B", addr_type)
        )
        # skip addr_type(1) + eir_len(2)
        return p[3:]

    # 0x003C — Read Extended Controller Index List
    def read_ext_ctrl_index_list(self) -> list[dict]:
        p = self.send_cmd_blocking(Cmd.READ_EXT_CTRL_INDEX_LIST)
        (n,) = struct.unpack("<H", p[:2])
        result = []
        for i in range(n):
            off = 2 + i * 4
            result.append(
                {
                    "index": struct.unpack("<H", p[off : off + 2])[0],
                    "type": p[off + 2],
                    "bus": p[off + 3],
                }
            )
        return result

    # 0x003D — Read Advertising Features
    def read_advertising_features(self, index: int) -> dict:
        p = self.send_cmd_blocking(Cmd.READ_ADVERTISING_FEATURES, index)
        sup_flags, max_adv, max_scan, max_inst, num_inst = struct.unpack(
            "<IBBBB", p[:8]
        )
        instances = list(p[8 : 8 + num_inst])
        return {
            "supported_flags": sup_flags,
            "max_adv_data_len": max_adv,
            "max_scan_rsp_len": max_scan,
            "max_instances": max_inst,
            "instances": instances,
        }

    # 0x003E — Add Advertising
    def add_advertising(
        self,
        index: int,
        instance: int,
        flags: int,
        duration: int,
        timeout: int,
        adv_data: bytes = b"",
        scan_rsp: bytes = b"",
    ) -> int:
        buf = struct.pack("<IBHH", instance, flags, duration, timeout)
        buf += struct.pack("<BB", len(adv_data), len(scan_rsp))
        buf += adv_data + scan_rsp
        p = self.send_cmd_blocking(Cmd.ADD_ADVERTISING, index, buf)
        return p[0]

    # 0x003F — Remove Advertising
    def remove_advertising(self, index: int, instance: int = 0) -> int:
        p = self.send_cmd_blocking(
            Cmd.REMOVE_ADVERTISING, index, struct.pack("<B", instance)
        )
        return p[0]

    # 0x0040 — Get Advertising Size Information
    def get_adv_size_info(self, index: int, instance: int, flags: int) -> dict:
        p = self.send_cmd_blocking(
            Cmd.GET_ADV_SIZE_INFO, index, struct.pack("<BI", instance, flags)
        )
        return {
            "instance": p[0],
            "flags": struct.unpack("<I", p[1:5])[0],
            "max_adv_data_len": p[5],
            "max_scan_rsp_len": p[6],
        }

    # 0x0041 — Start Limited Discovery
    def start_limited_discovery(self, index: int, addr_type: int) -> int:
        p = self.send_cmd_blocking(
            Cmd.START_LIMITED_DISCOVERY, index, struct.pack("<B", addr_type)
        )
        return p[0]

    # 0x0042 — Read Extended Controller Information
    def read_ext_ctrl_info(self, index: int) -> dict:
        p = self.send_cmd_blocking(Cmd.READ_EXT_CTRL_INFO, index)
        addr = ":".join(f"{b:02X}" for b in reversed(p[:6]))
        bt_ver = p[6]
        mfr = struct.unpack("<H", p[7:9])[0]
        sup, cur = struct.unpack("<II", p[9:17])
        eir_len = struct.unpack("<H", p[17:19])[0]
        eir = p[19 : 19 + eir_len]
        return {
            "address": addr,
            "bluetooth_version": bt_ver,
            "manufacturer": mfr,
            "supported_settings": sup,
            "current_settings": cur,
            "eir_data": eir,
        }

    # 0x0043 — Set Appearance
    def set_appearance(self, index: int, appearance: int) -> None:
        self.send_cmd_blocking(Cmd.SET_APPEARANCE, index, struct.pack("<H", appearance))

    # 0x0044 — Get PHY Configuration
    def get_phy_configuration(self, index: int) -> dict:
        p = self.send_cmd_blocking(Cmd.GET_PHY_CONFIGURATION, index)
        sup, cfg, sel = struct.unpack("<III", p[:12])
        return {"supported_phys": sup, "configurable_phys": cfg, "selected_phys": sel}

    # 0x0045 — Set PHY Configuration
    def set_phy_configuration(self, index: int, selected_phys: int) -> None:
        self.send_cmd_blocking(
            Cmd.SET_PHY_CONFIGURATION, index, struct.pack("<I", selected_phys)
        )

    # 0x0046 — Load Blocked Keys
    def load_blocked_keys(self, index: int, keys: list[tuple[int, bytes]]) -> None:
        """keys: (key_type, value(16))."""
        buf = struct.pack("<H", len(keys))
        for kt, val in keys:
            buf += struct.pack("<B", kt) + val
        self.send_cmd_blocking(Cmd.LOAD_BLOCKED_KEYS, index, buf)

    # 0x0047 — Set Wideband Speech
    def set_wideband_speech(self, index: int, enabled: bool) -> int:
        p = self.send_cmd_blocking(
            Cmd.SET_WIDEBAND_SPEECH, index, struct.pack("<B", int(enabled))
        )
        return struct.unpack("<I", p)[0]

    # 0x0048 — Read Controller Capabilities
    def read_ctrl_capabilities(self, index: int) -> bytes:
        p = self.send_cmd_blocking(Cmd.READ_CTRL_CAPABILITIES, index)
        eir_len = struct.unpack("<H", p[:2])[0]
        return p[2 : 2 + eir_len]

    # 0x0049 — Read Experimental Features Information
    def read_exp_features_info(self, index: int = HCI_DEV_NONE) -> list[dict]:
        p = self.send_cmd_blocking(Cmd.READ_EXP_FEATURES_INFO, index)
        (n,) = struct.unpack("<H", p[:2])
        result = []
        for i in range(n):
            off = 2 + i * 20
            uuid = p[off : off + 16]
            flags = struct.unpack("<I", p[off + 16 : off + 20])[0]
            result.append({"uuid": uuid, "flags": flags})
        return result

    # 0x004A — Set Experimental Feature
    def set_exp_feature(
        self, uuid: bytes, action: int, index: int = HCI_DEV_NONE
    ) -> tuple[bytes, int]:
        if len(uuid) != 16:
            raise ValueError("UUID must be 16 bytes")
        p = self.send_cmd_blocking(
            Cmd.SET_EXP_FEATURE, index, uuid + struct.pack("<B", action)
        )
        return p[:16], struct.unpack("<I", p[16:20])[0]

    # 0x004B — Read Default System Configuration
    def read_default_sys_config(self, index: int) -> list[dict]:
        p = self.send_cmd_blocking(Cmd.READ_DEFAULT_SYS_CONFIG, index)
        params = []
        off = 0
        while off + 3 <= len(p):
            pt = struct.unpack("<H", p[off : off + 2])[0]
            off += 2
            vl = p[off]
            off += 1
            val = p[off : off + vl]
            off += vl
            params.append({"type": pt, "value": val})
        return params

    # 0x004C — Set Default System Configuration
    def set_default_sys_config(
        self, index: int, params: list[tuple[int, bytes]]
    ) -> None:
        buf = b""
        for pt, val in params:
            buf += struct.pack("<HB", pt, len(val)) + val
        self.send_cmd_blocking(Cmd.SET_DEFAULT_SYS_CONFIG, index, buf)

    # 0x004D — Read Default Runtime Configuration
    def read_default_runtime_config(self, index: int) -> list[dict]:
        p = self.send_cmd_blocking(Cmd.READ_DEFAULT_RUNTIME_CONFIG, index)
        params = []
        off = 0
        while off + 3 <= len(p):
            pt = struct.unpack("<H", p[off : off + 2])[0]
            off += 2
            vl = p[off]
            off += 1
            val = p[off : off + vl]
            off += vl
            params.append({"type": pt, "value": val})
        return params

    # 0x004E — Set Default Runtime Configuration
    def set_default_runtime_config(
        self, index: int, params: list[tuple[int, bytes]]
    ) -> None:
        buf = b""
        for pt, val in params:
            buf += struct.pack("<HB", pt, len(val)) + val
        self.send_cmd_blocking(Cmd.SET_DEFAULT_RUNTIME_CONFIG, index, buf)

    # 0x004F — Get Device Flags
    def get_device_flags(self, index: int, addr: bytes, addr_type: int) -> dict:
        p = self.send_cmd_blocking(
            Cmd.GET_DEVICE_FLAGS, index, addr + struct.pack("<B", addr_type)
        )
        sup, cur = struct.unpack("<II", p[7:])
        return {"supported_flags": sup, "current_flags": cur}

    # 0x0050 — Set Device Flags
    def set_device_flags(
        self, index: int, addr: bytes, addr_type: int, current_flags: int
    ) -> tuple[bytes, int]:
        p = self.send_cmd_blocking(
            Cmd.SET_DEVICE_FLAGS,
            index,
            addr + struct.pack("<BI", addr_type, current_flags),
        )
        return p[:6], p[6]

    # 0x0051 — Read Advertisement Monitor Features
    def read_adv_monitor_features(self, index: int) -> dict:
        p = self.send_cmd_blocking(Cmd.READ_ADV_MONITOR_FEATURES, index)
        sup, ena, max_h, max_p, num_h = struct.unpack("<IIHBHH", p[:14])
        handles = list(struct.unpack(f"<{num_h}H", p[14 : 14 + num_h * 2]))
        return {
            "supported_features": sup,
            "enabled_features": ena,
            "max_handles": max_h,
            "max_patterns": max_p,
            "handles": handles,
        }

    # 0x0052 — Add Advertisement Patterns Monitor
    def add_adv_patterns_monitor(
        self, index: int, patterns: list[tuple[int, int, int, bytes]]
    ) -> int:
        """patterns: (ad_type, offset, length, value)."""
        buf = struct.pack("<B", len(patterns))
        for ad_type, offset, length, value in patterns:
            buf += struct.pack("<BBB", ad_type, offset, length)
            buf += value.ljust(31, b"\x00")
        p = self.send_cmd_blocking(Cmd.ADD_ADV_PATTERNS_MONITOR, index, buf)
        return struct.unpack("<H", p[:2])[0]

    # 0x0053 — Remove Advertisement Monitor
    def remove_adv_monitor(self, index: int, monitor_handle: int = 0) -> int:
        p = self.send_cmd_blocking(
            Cmd.REMOVE_ADV_MONITOR, index, struct.pack("<H", monitor_handle)
        )
        return struct.unpack("<H", p[:2])[0]

    # 0x0054 — Add Extended Advertising Parameters
    def add_ext_adv_parameters(
        self,
        index: int,
        instance: int,
        flags: int,
        duration: int,
        timeout: int,
        min_interval: int = 0,
        max_interval: int = 0,
        tx_power: int = 127,
    ) -> dict:
        buf = struct.pack(
            "<IBHHIIB",
            instance,
            flags,
            duration,
            timeout,
            min_interval,
            max_interval,
            tx_power,
        )
        p = self.send_cmd_blocking(Cmd.ADD_EXT_ADV_PARAMETERS, index, buf)
        return {
            "instance": p[0],
            "tx_power": p[1],
            "max_adv_data_len": p[2],
            "max_scan_rsp_len": p[3],
        }

    # 0x0055 — Add Extended Advertising Data
    def add_ext_adv_data(
        self, index: int, instance: int, adv_data: bytes = b"", scan_rsp: bytes = b""
    ) -> int:
        buf = struct.pack("<BBB", instance, len(adv_data), len(scan_rsp))
        buf += adv_data + scan_rsp
        p = self.send_cmd_blocking(Cmd.ADD_EXT_ADV_DATA, index, buf)
        return p[0]

    # 0x0056 — Add Adv Patterns Monitor With RSSI Threshold
    def add_adv_patterns_monitor_rssi(
        self,
        index: int,
        high_threshold: int,
        high_timer: int,
        low_threshold: int,
        low_timer: int,
        sampling_period: int,
        patterns: list[tuple[int, int, int, bytes]],
    ) -> int:
        buf = struct.pack(
            "<bHbHB",
            high_threshold,
            high_timer,
            low_threshold,
            low_timer,
            sampling_period,
        )
        buf += struct.pack("<B", len(patterns))
        for ad_type, offset, length, value in patterns:
            buf += struct.pack("<BBB", ad_type, offset, length)
            buf += value.ljust(31, b"\x00")
        p = self.send_cmd_blocking(Cmd.ADD_ADV_PATTERNS_MONITOR_RSSI, index, buf)
        return struct.unpack("<H", p[:2])[0]

    # 0x0057 — Set Mesh Receiver
    def set_mesh_receiver(
        self, index: int, enable: bool, window: int, period: int, ad_types: list[int]
    ) -> None:
        buf = struct.pack("<BHHB", int(enable), window, period, len(ad_types))
        buf += bytes(ad_types)
        self.send_cmd_blocking(Cmd.SET_MESH_RECEIVER, index, buf)

    # 0x0058 — Read Mesh Features
    def read_mesh_features(self, index: int) -> dict:
        p = self.send_cmd_blocking(Cmd.READ_MESH_FEATURES, index)
        idx = struct.unpack("<H", p[:2])[0]
        max_h, used_h = p[2], p[3]
        handles = list(p[4 : 4 + used_h])
        return {
            "index": idx,
            "max_handles": max_h,
            "used_handles": used_h,
            "handles": handles,
        }

    # 0x0059 — Transmit Mesh Packet
    def transmit_mesh_packet(
        self,
        index: int,
        addr: bytes,
        addr_type: int,
        instant: int,
        delay: int,
        count: int,
        data: bytes,
    ) -> int:
        buf = addr + struct.pack("<BQHB", addr_type, instant, delay, count)
        buf += struct.pack("<B", len(data)) + data
        p = self.send_cmd_blocking(Cmd.TRANSMIT_MESH_PACKET, index, buf)
        return p[0]

    # 0x005A — Cancel Transmit Mesh Packet
    def cancel_transmit_mesh_packet(self, index: int, handle: int = 0) -> None:
        self.send_cmd_blocking(
            Cmd.CANCEL_TRANSMIT_MESH_PACKET, index, struct.pack("<B", handle)
        )

    # 0x005B — Send HCI Command
    def send_hci_cmd(
        self, index: int, opcode: int, event: int, timeout: int, params: bytes
    ) -> bytes:
        buf = struct.pack("<HBBH", opcode, event, timeout, len(params))
        buf += params
        p = self.send_cmd_blocking(Cmd.SEND_HCI_CMD, index, buf)
        return p

    # ── Cleanup ───────────────────────────────────────────────────────

    def close(self) -> None:
        """Close the mgmt socket."""
        if self._sock:
            self._sock.close()

    def fileno(self) -> int:
        """Return the socket's file descriptor for select/poll compatibility."""
        return self._sock.fileno()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
