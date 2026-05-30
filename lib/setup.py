from setuptools import setup, Extension
from Cython.Build import cythonize

setup(
    name="lib",
    ext_modules=cythonize(
        [
            Extension(
                "lib.bumble.hci",
                sources=["lib/bumble/hci.pyx"],
            ),
            Extension(
                "lib.bumble.l2cap",
                sources=["lib/bumble/l2cap.pyx"],
            ),
            Extension(
                "lib.Xlib.protocol.request",
                sources=["lib/Xlib/protocol/request.pyx"],
            ),
        ]
    ),
)
