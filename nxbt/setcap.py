import ctypes
import ctypes.util
import os

if ctypes.util.find_library("cap"):
    libcap = ctypes.CDLL(ctypes.util.find_library("cap"), use_errno=True)
    libcap.cap_from_text.argtypes = [ctypes.c_char_p]
    libcap.cap_from_text.restype = ctypes.c_void_p
    libcap.cap_get_file.argtypes = [ctypes.c_char_p]
    libcap.cap_get_file.restype = ctypes.c_void_p
    libcap.cap_to_text.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
    libcap.cap_to_text.restype = ctypes.c_char_p
    libcap.cap_set_file.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
    libcap.cap_set_file.restype = ctypes.c_int
    libcap.cap_free.argtypes = [ctypes.c_void_p]
    libcap.cap_free.restype = ctypes.c_int
else:
    libcap = None

GRANT_CAPS_HINT = 'Run `sudo env HOME="$HOME" nxbt` first to grant permissions.'


def get_file_cap(path: str) -> str | None:
    if not libcap:
        return None
    cap = libcap.cap_get_file(os.fsencode(path))
    if not cap:
        return None
    try:
        text = libcap.cap_to_text(cap, None)
        return text.decode() if text else None
    finally:
        libcap.cap_free(cap)


def get_executable_caps() -> str | None:
    try:
        return get_file_cap(os.readlink("/proc/self/exe"))
    except (OSError, AttributeError):
        return None


def _caps_include(cap_text: str | None, *caps: str) -> bool:
    if not cap_text:
        return False
    return all(cap in cap_text for cap in caps)


def has_cap_net_admin() -> bool:
    return _caps_include(get_executable_caps(), "cap_net_admin")


def has_bluez_caps() -> bool:
    return _caps_include(get_executable_caps(), "cap_net_admin", "cap_net_bind_service")


def set_file_cap(path: str, spec: str) -> None:
    if not libcap:
        return
    cap = libcap.cap_from_text(spec.encode())
    if not cap:
        raise OSError("cap_from_text failed")
    try:
        if libcap.cap_set_file(os.fsencode(path), cap) != 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err))
    finally:
        libcap.cap_free(cap)
