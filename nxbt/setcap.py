import ctypes
import ctypes.util
import os

if ctypes.util.find_library("cap"):
    libcap = ctypes.CDLL(ctypes.util.find_library("cap"), use_errno=True)
    libcap.cap_from_text.argtypes = [ctypes.c_char_p]
    libcap.cap_from_text.restype = ctypes.c_void_p
    libcap.cap_set_file.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
    libcap.cap_set_file.restype = ctypes.c_int
    libcap.cap_free.argtypes = [ctypes.c_void_p]
    libcap.cap_free.restype = ctypes.c_int
else:
    libcap = None


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
