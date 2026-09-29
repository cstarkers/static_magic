"""Versioned bindings for libmagic, statically linked and shipped with their database.

The libmagic version this was built against is the first two components of this
package's version, so static_magic 5.45.* is always libmagic 5.45.
"""

from __future__ import annotations

import atexit
import os
import threading
from collections.abc import Buffer
from contextlib import ExitStack
from importlib.resources import as_file, files

from . import _magic

__all__ = [
    "MAGIC_DB",
    "Magic",
    "libmagic_version",
    "get_description_file",
    "get_mime_type_file",
    "get_description_bytes",
    "get_mime_type_bytes",
]

StrOrBytesPath = str | bytes | os.PathLike[str] | os.PathLike[bytes]

# libmagic needs a real filesystem path, but importlib.resources hands back a
# Traversable that isn't guaranteed to be one. as_file() materialises it; the
# ExitStack keeps it alive for the process lifetime. In practice this package
# always unpacks to a real directory (extension modules can't be imported from
# a zip), so this is a no-op -- but it's the correct no-op.
_resources = ExitStack()
atexit.register(_resources.close)
MAGIC_DB = str(_resources.enter_context(as_file(files(__package__) / "magic.mgc")))


def libmagic_version() -> int:
    """Return the version of the bundled libmagic, e.g. 545 for 5.45."""
    return _magic.libmagic_version()


class Magic:
    """A loaded libmagic database.

    Loading the database is the expensive part, so create one of these and reuse
    it. Instances are safe to share between threads; calls on the same instance
    are serialised.

    Missing or unreadable files raise OSError (e.g. FileNotFoundError).
    """

    def __init__(self, *, database: StrOrBytesPath = MAGIC_DB) -> None:
        self._magic = _magic.init_magic(database)
        # libmagic handles are not reentrant, and each query sets the handle's flags.
        self._lock = threading.Lock()

    def get_description_file(self, path: StrOrBytesPath) -> str:
        """Describe the file at `path`, e.g. "ELF 64-bit LSB pie executable, ..."."""
        with self._lock:
            return _magic.describe_file(self._magic, path, False)

    def get_mime_type_file(self, path: StrOrBytesPath) -> str:
        """Return the MIME type of the file at `path`, e.g. "application/pdf"."""
        with self._lock:
            return _magic.describe_file(self._magic, path, True)

    def get_description_bytes(self, data: Buffer) -> str:
        """Describe the contents of `data`."""
        with self._lock:
            return _magic.describe_bytes(self._magic, data, False)

    def get_mime_type_bytes(self, data: Buffer) -> str:
        """Return the MIME type of the contents of `data`."""
        with self._lock:
            return _magic.describe_bytes(self._magic, data, True)


_default_magic: Magic | None = None
_default_lock = threading.Lock()


def _default() -> Magic:
    # Loading the database is expensive, so make sure concurrent first calls
    # (which really are concurrent on free-threaded builds) only load it once.
    global _default_magic
    if _default_magic is None:
        with _default_lock:
            if _default_magic is None:
                _default_magic = Magic()
    return _default_magic


def get_description_file(path: StrOrBytesPath) -> str:
    """Describe the file at `path` using a shared default Magic."""
    return _default().get_description_file(path)


def get_mime_type_file(path: StrOrBytesPath) -> str:
    """Return the MIME type of the file at `path` using a shared default Magic."""
    return _default().get_mime_type_file(path)


def get_description_bytes(data: Buffer) -> str:
    """Describe the contents of `data` using a shared default Magic."""
    return _default().get_description_bytes(data)


def get_mime_type_bytes(data: Buffer) -> str:
    """Return the MIME type of the contents of `data` using a shared default Magic."""
    return _default().get_mime_type_bytes(data)
