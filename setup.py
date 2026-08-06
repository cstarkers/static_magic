from distutils.core import setup, Extension

module = Extension("py_magic", sources=["src/magicmodule.c"])

setup(
    name="py_magic",
    version="0.1",
    description="An example of C extension made callable to the Python API.",
    ext_modules=[module],
)
