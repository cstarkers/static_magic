import gc
import os
import sys
import sysconfig
import threading
from importlib.metadata import version

import pytest

import py_magic

SETUP_PY = os.path.join(os.path.dirname(__file__), "..", "setup.py")
PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"


def test_database_is_shipped():
    assert os.path.isfile(py_magic.MAGIC_DB)


def test_libmagic_version_matches_package_version():
    # The package promises py_magic X.Y.* bundles libmagic X.Y.
    major, minor = version("py_magic").split(".")[:2]
    assert py_magic.libmagic_version() == int(major) * 100 + int(minor)


@pytest.mark.skipif(
    not sysconfig.get_config_var("Py_GIL_DISABLED"), reason="needs a free-threaded build"
)
def test_import_keeps_gil_disabled():
    # py_magic was imported at the top of this file; an extension without the
    # Py_mod_gil slot would have switched the GIL back on at that point.
    assert not sys._is_gil_enabled()


def test_describe_file():
    assert "Python script" in py_magic.get_description_file(SETUP_PY)
    assert py_magic.get_mime_type_file(SETUP_PY) == "text/x-script.python"


def test_describe_bytes():
    assert py_magic.get_description_bytes(PDF) == "PDF document, version 1.4"
    assert py_magic.get_mime_type_bytes(memoryview(PDF)) == "application/pdf"


def test_missing_file_raises(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError) as info:
        py_magic.Magic().get_description_file(missing)
    assert info.value.filename == missing


def test_bad_database_raises(tmp_path):
    with pytest.raises(RuntimeError):
        py_magic.Magic(database=tmp_path / "missing.mgc")


def test_handles_are_released():
    for _ in range(20):
        py_magic.Magic().get_mime_type_file(SETUP_PY)
    gc.collect()


def test_shared_instance_across_threads():
    # Mixed mime/description queries on one instance must not race on flags.
    m = py_magic.Magic()
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
