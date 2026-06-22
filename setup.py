from setuptools import setup, Extension
from Cython.Build import cythonize
import shutil
import platform
import sys

if shutil.which("ccache") is not None:
    import os

    os.environ["CC"] = "ccache gcc"
else:
    print("Warning: without ccache reprepare nxbt would be much slower")

extra_compile_args = []
extra_link_args = []
setup_options = {}

if platform.machine() in ("armv7", "armv7l"):
    # Resolve `Error: conditional branch out of range`
    extra_compile_args = ["-marm"]
    extra_link_args = ["-marm"]
if sys.platform == "win32":
    setup_options["build_ext"] = {"compiler": "mingw32"}

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
    options=setup_options,
)
