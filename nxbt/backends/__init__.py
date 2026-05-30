import platform

from .base import Backend

from .bumble import BumbleBackend

if platform.system() == "Linux":
    from .bluez import BlueZBackend

    __all__ = ["Backend", "BlueZBackend", "BumbleBackend", "BACKENDS"]
    BACKENDS = {"bluez": BlueZBackend, "bumble": BumbleBackend}
else:
    __all__ = ["Backend", "BumbleBackend", "BACKENDS"]
    BACKENDS = {"bumble": BumbleBackend}
