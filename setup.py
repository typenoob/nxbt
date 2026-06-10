from setuptools import setup, Extension
from Cython.Build import cythonize
import shutil
import platform

if shutil.which("ccache") is not None:
    import os

    os.environ["CC"] = "ccache gcc"
else:
    print("Warning: without ccache reprepare nxbt would be much slower")

extra_compile_args = []
extra_link_args = []
if platform.machine() in ("armv7", "armv7l"):
    # Resolve `Error: conditional branch out of range`
    extra_compile_args = ["-marm"]
    extra_link_args = ["-marm"]

setup(
    name="lib",
    ext_modules=cythonize(
        [
            Extension(
                "lib.bumble.hci",
                sources=["lib/bumble/hci.pyx"],
                extra_compile_args=extra_compile_args,
                extra_link_args=extra_link_args,
            ),
            Extension(
                "lib.bumble.l2cap",
                sources=["lib/bumble/l2cap.pyx"],
                extra_compile_args=extra_compile_args,
                extra_link_args=extra_link_args,
            ),
        ]
    ),
)
