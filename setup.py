from setuptools import setup, Extension
from Cython.Build import cythonize
import shutil

if shutil.which("ccache") is not None:
    import os

    os.environ["CC"] = "ccache gcc"
else:
    print("Warning: without ccache reprepare nxbt would be much slower")

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
        ]
    ),
)
