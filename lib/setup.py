from setuptools import setup, Extension
from Cython.Build import cythonize

setup(
    name="lib",
    ext_modules=cythonize(
        Extension(
            "lib.bumble.hci",
            sources=["lib/bumble/hci.pyx"],
        )
    ),
)
