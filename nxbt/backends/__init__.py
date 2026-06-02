from .internal.tools import has_tool

from .base import Backend

from .bumble import BumbleBackend

if has_tool("bluetoothd"):
    from .bluez import BlueZBackend

    __all__ = ["Backend", "BlueZBackend", "BumbleBackend", "BACKENDS"]
    BACKENDS = {"bluez": BlueZBackend, "bumble": BumbleBackend}
else:
    __all__ = ["Backend", "BumbleBackend", "BACKENDS"]
    BACKENDS = {"bumble": BumbleBackend}
