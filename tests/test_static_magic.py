import gc
import os
import sys
import sysconfig
import threading
from importlib.metadata import version

import pytest

import static_magic

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"


@pytest.fixture
def script(tmp_path):
    # The tests run against an installed wheel, away from the source tree, so
    # they bring their own sample file rather than pointing at one in the repo.
    path = tmp_path / "script.py"
    path.write_text("#!/usr/bin/env python3\nimport sys\n\nprint(sys.argv)\n")
    return path


def test_database_is_shipped():
    assert os.path.isfile(static_magic.MAGIC_DB)


def test_libmagic_version_matches_package_version():
    # The package promises static_magic X.Y.* bundles libmagic X.Y.
    major, minor = version("static_magic").split(".")[:2]
    assert static_magic.libmagic_version() == int(major) * 100 + int(minor)


@pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"), reason="needs a free-threaded build"
)
def test_import_keeps_gil_disabled():
    # static_magic was imported at the top of this file; an extension without the
    # Py_mod_gil slot would have switched the GIL back on at that point.
    assert not sys._is_gil_enabled()


def test_describe_file(script):
    assert "Python script" in static_magic.get_description_file(script)
    assert static_magic.get_mime_type_file(script) == "text/x-script.python"


def test_describe_bytes():
    assert static_magic.get_description_bytes(PDF) == "PDF document, version 1.4"
    assert static_magic.get_mime_type_bytes(memoryview(PDF)) == "application/pdf"


def test_database_is_the_shipped_one():
    # Two equal-strength rules match a NumPy header, and which one answers
    # depends on the order they were compiled in, which depends on the C
    # library that compiled the database. Every wheel ships the database
    # compiled with the sdist (on Linux), so this answer must be the same on
    # every platform; a macOS-compiled database says "NumPy data file" instead.
    header = b"{'descr': '<f8', 'fortran_order': False, 'shape': (2,), }".ljust(69) + b"\n"
    npy = b"\x93NUMPY\x01\x00" + len(header).to_bytes(2, "little") + header + bytes(16)
    assert static_magic.get_description_bytes(npy) == "NumPy array, version 1.0, header length 70"


def test_missing_file_raises(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError) as info:
        static_magic.Magic().get_description_file(missing)
    assert info.value.filename == missing


def test_bad_database_raises(tmp_path):
    with pytest.raises(RuntimeError):
        static_magic.Magic(database=tmp_path / "missing.mgc")


def test_handles_are_released(script):
    for _ in range(20):
        static_magic.Magic().get_mime_type_file(script)
    gc.collect()


def test_shared_instance_across_threads():
    # Mixed mime/description queries on one instance must not race on flags.
    m = static_magic.Magic()
    errors = []

    def worker(mime):
        for _ in range(50):
            got = m.get_mime_type_bytes(PDF) if mime else m.get_description_bytes(PDF)
            expected = "application/pdf" if mime else "PDF document, version 1.4"
            if got != expected:
                errors.append(got)

    threads = [threading.Thread(target=worker, args=(i % 2 == 0,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
