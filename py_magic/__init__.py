"""Versioned bindings for libmagic, statically linked and shipped with their database.

The libmagic version this was built against is the first two components of this
package's version, so py_magic 5.45.* is always libmagic 5.45.
"""

import atexit
from contextlib import ExitStack
from importlib.resources import as_file, files

from . import _magic

__all__ = ["MAGIC_DB", "get_magic_number", "get_magic_mime_type_file", "get_magic_description_file"]

# libmagic needs a real filesystem path, but importlib.resources hands back a
# Traversable that isn't guaranteed to be one. as_file() materialises it; the
# ExitStack keeps it alive for the process lifetime. In practice this package
# always unpacks to a real directory (extension modules can't be imported from
# a zip), so this is a no-op -- but it's the correct no-op.
_resources = ExitStack()
atexit.register(_resources.close)
MAGIC_DB = str(_resources.enter_context(as_file(files(__package__) / "magic.mgc")))


def get_magic_number():
    """Return the magic number."""
    return _magic.get_magic_number()


def get_magic_description_file(path):
    """Describe the file at `path`.

    With is_mime=False (the default) this is the descriptive string, e.g.
    "ELF 64-bit LSB pie executable, x86-64, ...". With is_mime=True it's the
    MIME type, e.g. "application/x-pie-executable".
    """
    return _magic.get_magic_for_file(MAGIC_DB, path, False)

def get_magic_mime_type_file(path):
    """Describe the file at `path`.

    With is_mime=False (the default) this is the descriptive string, e.g.
    "ELF 64-bit LSB pie executable, x86-64, ...". With is_mime=True it's the
    MIME type, e.g. "application/x-pie-executable".
    """
    return _magic.get_magic_for_file(MAGIC_DB, path, True)
