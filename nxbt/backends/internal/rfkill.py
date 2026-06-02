"""Userspace rfkill interface via /dev/rfkill.

Provides a Python binding to the kernel rfkill subsystem using the
``/dev/rfkill`` character device.  This replaces the subprocess-based
``rfkill list`` parsing in ``tools.get_blocked_hci_indices()`` with a
direct read/write API that also supports real-time event monitoring
via ``poll()``.

Struct layout (``struct rfkill_event``, packed, little-endian)::

    __u32 idx;   # device index
    __u8  type;  # RFKILL_TYPE_*
    __u8  op;    # RFKILL_OP_*
    __u8  soft;  # soft-block state (0/1)
    __u8  hard;  # hard-block state (0/1)

Total: 8 bytes.

See ``linux/rfkill.h`` for the canonical C definition.
"""

import fcntl
import logging
import os
import re
import select
import struct
from enum import IntEnum
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nxbt")

# ---------------------------------------------------------------------------
# Constants (mirroring linux/rfkill.h)
# ---------------------------------------------------------------------------

RFKILL_DEV = "/dev/rfkill"
RFKILL_EVENT_SIZE_V1 = 8  # sizeof(struct rfkill_event), packed


class RfkillType(IntEnum):
    """RF kill switch types."""

    ALL = 0
    WLAN = 1
    BLUETOOTH = 2
    UWB = 3
    WIMAX = 4
    WWAN = 5
    GPS = 6
    FM = 7
    NFC = 8


class RfkillOp(IntEnum):
    """RF kill operation codes."""

    ADD = 0
    DEL = 1
    CHANGE = 2
    CHANGE_ALL = 3


class RfkillState(IntEnum):
    """Legacy rfkill states ( informational only; soft/hard are now separate)."""

    SOFT_BLOCKED = 0
    UNBLOCKED = 1
    HARD_BLOCKED = 2


# ioctl: turn off the deprecated rfkill input handler
_RFKILL_IOC_MAGIC = ord("R")
_RFKILL_IOC_NOINPUT = 1
RFKILL_IOCTL_NOINPUT = _RFKILL_IOC_MAGIC << 8 | _RFKILL_IOC_NOINPUT

# Event struct format: little-endian uint32 + 4 x uint8
_EVENT_FMT = "<IBBBB"


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


class RfkillDevice:
    """Represents a single rfkill switch entry.

    Attributes:
        idx: Kernel-assigned device index.
        type: Device type (``RfkillType``).
        op: Last operation (``RfkillOp``).
        soft_blocked: ``True`` when the device is soft-blocked.
        hard_blocked: ``True`` when the device is hard-blocked.
    """

    __slots__ = ("idx", "type", "op", "soft_blocked", "hard_blocked")

    def __init__(
        self,
        idx: int = 0,
        type: RfkillType = RfkillType.ALL,
        op: RfkillOp = RfkillOp.ADD,
        soft_blocked: bool = False,
        hard_blocked: bool = False,
    ):
        self.idx = idx
        self.type = type
        self.op = op
        self.soft_blocked = soft_blocked
        self.hard_blocked = hard_blocked

    @property
    def blocked(self) -> bool:
        """``True`` when either soft- or hard-blocked."""
        return self.soft_blocked or self.hard_blocked

    def _unpack(self, data: bytes) -> None:
        """Populate fields from a packed ``struct rfkill_event``."""
        idx, typ, op, soft, hard = struct.unpack(_EVENT_FMT, data)
        self.idx = idx
        self.type = RfkillType(typ)
        self.op = RfkillOp(op)
        self.soft_blocked = bool(soft)
        self.hard_blocked = bool(hard)

    def pack(self) -> bytes:
        """Serialize to a packed ``struct rfkill_event`` for writing."""
        return struct.pack(
            _EVENT_FMT,
            self.idx,
            int(self.type),
            int(self.op),
            int(self.soft_blocked),
            int(self.hard_blocked),
        )

    def __repr__(self) -> str:
        return (
            f"RfkillDevice(idx={self.idx}, type={self.type.name}, "
            f"op={self.op.name}, soft_blocked={self.soft_blocked}, "
            f"hard_blocked={self.hard_blocked})"
        )


# ---------------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------------


class RfkillClient:
    """Client for the ``/dev/rfkill`` userspace API.

    Open the device once, then read all current device states from the
    initial stream.  Subsequent reads / ``poll()`` calls yield hot-plug
    and state-change events.

    Example::

        with RfkillClient() as rfkill:
            for dev in rfkill.list_devices():
                print(dev)

            # unblock all bluetooth adapters
            rfkill.set_sw_state(RfkillType.BLUETOOTH, soft_blocked=False)
    """

    def __init__(self, device_path: str = RFKILL_DEV):
        self._device_path = device_path
        self._fd: Optional[int] = None

    # -- context manager ---------------------------------------------------

    def open(self) -> None:
        """Open ``/dev/rfkill`` for reading and writing."""
        self._fd = os.open(self._device_path, os.O_RDWR)

    def close(self) -> None:
        """Close the device file descriptor."""
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self) -> "RfkillClient":
        self.open()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    @property
    def fileno(self) -> int:
        """File descriptor for use with ``select.poll()``."""
        if self._fd is None:
            raise OSError("rfkill device is not open")
        return self._fd

    # -- core I/O -----------------------------------------------------------

    def _read_event(self) -> Optional[RfkillDevice]:
        """Read a single ``rfkill_event`` from the device.

        Returns ``None`` when no data is available (non-blocking mode) or
        on a short read.
        """
        if self._fd is None:
            raise OSError("rfkill device is not open")
        try:
            data = os.read(self._fd, RFKILL_EVENT_SIZE_V1)
        except BlockingIOError:
            return None
        if len(data) < RFKILL_EVENT_SIZE_V1:
            return None
        dev = RfkillDevice()
        dev._unpack(data)
        return dev

    def _write_event(self, event: RfkillDevice) -> int:
        """Write a ``rfkill_event`` to the device.

        Returns the number of bytes written.
        """
        if self._fd is None:
            raise OSError("rfkill device is not open")
        return os.write(self._fd, event.pack())

    # -- public API ---------------------------------------------------------

    def list_devices(self) -> list[RfkillDevice]:
        """Return the current state of all rfkill devices.

        On open, the kernel streams all existing device states as ``ADD``
        events.  This method drains them all into a list.
        """
        if self._fd is None:
            self.open()

        devices: list[RfkillDevice] = []
        # Drain all immediately-available events.
        while True:
            # Use poll with a short timeout to avoid blocking forever.
            poller = select.poll()
            poller.register(self._fd, select.POLLIN)
            events = poller.poll(50)  # 50 ms
            if not events:
                break
            dev = self._read_event()
            if dev is not None:
                devices.append(dev)
        return devices

    def wait_event(self, timeout_ms: int = -1) -> Optional[RfkillDevice]:
        """Block until a new rfkill event arrives (or timeout).

        Args:
            timeout_ms: Milliseconds to wait (``-1`` = forever).

        Returns:
            The new ``RfkillDevice`` event, or ``None`` on timeout.
        """
        if self._fd is None:
            raise OSError("rfkill device is not open")
        poller = select.poll()
        poller.register(self._fd, select.POLLIN)
        ready = poller.poll(timeout_ms)
        if not ready:
            return None
        return self._read_event()

    def set_sw_state(
        self,
        rfkill_type: RfkillType,
        soft_blocked: bool = True,
    ) -> None:
        """Set the soft-block state for all devices of a given type.

        This sends a ``CHANGE_ALL`` event which also updates the default
        state for devices hot-plugged later.

        Args:
            rfkill_type: Which device class to affect.
            soft_blocked: ``True`` to soft-block, ``False`` to unblock.
        """
        event = RfkillDevice(
            type=rfkill_type,
            op=RfkillOp.CHANGE_ALL,
            soft_blocked=soft_blocked,
        )
        self._write_event(event)
        logger.debug(
            "rfkill: set_sw_state type=%s soft_blocked=%s",
            rfkill_type.name,
            soft_blocked,
        )

    def unblock_type(self, rfkill_type: RfkillType) -> None:
        """Unblock all devices of *rfkill_type* (clear soft block)."""
        self.set_sw_state(rfkill_type, soft_blocked=False)

    def block_type(self, rfkill_type: RfkillType) -> None:
        """Soft-block all devices of *rfkill_type*."""
        self.set_sw_state(rfkill_type, soft_blocked=True)

    def disable_input_handler(self) -> None:
        """Disable the deprecated rfkill input handler via ioctl.

        This prevents the kernel's rfkill-input module from intercepting
        events.  Only relevant during migration from older systems.
        """
        if self._fd is None:
            raise OSError("rfkill device is not open")
        try:
            fcntl.ioctl(self._fd, RFKILL_IOCTL_NOINPUT)
            logger.debug("rfkill: disabled kernel input handler")
        except OSError:
            logger.debug("rfkill: kernel input handler already disabled or unavailable")


# ---------------------------------------------------------------------------
# Convenience functions (drop-in helpers for tools.py)
# ---------------------------------------------------------------------------


def get_blocked_hci_indices() -> set[int]:
    """Return HCI adapter indices that are rfkill-blocked.

    Opens ``/dev/rfkill``, reads all devices, and returns the HCI adapter
    numbers (from sysfs) of Bluetooth-type devices that are either soft-
    or hard-blocked.

    Returns:
        A set of blocked Bluetooth HCI adapter indices (e.g. ``{0, 2}``).
        Returns an empty set if ``/dev/rfkill`` is unavailable.
    """
    blocked: set[int] = set()
    try:
        with RfkillClient() as rfkill:
            for dev in rfkill.list_devices():
                if dev.type == RfkillType.BLUETOOTH and dev.blocked:
                    hci_id = _rfkill_to_hci_id(dev.idx)
                    if hci_id is not None:
                        blocked.add(hci_id)
    except (OSError, PermissionError):
        logger.debug("rfkill: /dev/rfkill unavailable, returning empty blocked set")
    return blocked


def _rfkill_to_hci_id(rfkill_idx: int) -> Optional[int]:
    """Map an rfkill device index to an HCI adapter number via sysfs.

    Reads ``/sys/class/rfkill/rfkill{N}/name`` which contains strings like
    ``hci0``, ``hci1``, etc.  Returns the numeric HCI adapter ID, or
    ``None`` if the sysfs entry is unreadable or the name is not an HCI
    device.
    """
    name_path = Path(f"/sys/class/rfkill/rfkill{rfkill_idx}/name")
    try:
        name = name_path.read_text().strip()
    except (OSError, PermissionError):
        logger.debug("rfkill: cannot read %s", name_path)
        return None
    m = re.match(r"^hci(\d+)$", name)
    if m:
        return int(m.group(1))
    logger.debug("rfkill: rfkill%d name=%r is not an HCI device", rfkill_idx, name)
    return None


def unblock_bluetooth() -> None:
    """Clear the soft-block state for all Bluetooth rfkill devices."""
    try:
        with RfkillClient() as rfkill:
            rfkill.unblock_type(RfkillType.BLUETOOTH)
            logger.info("rfkill: unblocked all Bluetooth adapters")
    except (OSError, PermissionError) as exc:
        logger.warning("rfkill: could not unblock Bluetooth: %s", exc)
