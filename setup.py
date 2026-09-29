import os, re, shutil, subprocess
from pathlib import Path
from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext

HERE = Path(__file__).parent.resolve()
FILE_SRC = HERE / "third_party" / "file"

CONFIGURE_ARGS = [
  "--disable-shared", "--enable-static", "--with-pic",
  "--disable-zlib", "--disable-bzlib", "--disable-xzlib",
  "--disable-zstdlib", "--disable-lzlib", "--disable-libseccomp",
  "--disable-dependency-tracking",
]

def libmagic_version():
  text = (FILE_SRC / "configure.ac").read_text()
  return re.search(r"AC_INIT\(\[file\],\[([^\]]+)\]", text).group(1)


class build_ext_static_magic(build_ext):
    def run(self):
        if not (FILE_SRC / "configure.ac").exists():
          raise SystemExit("third_party/file is empty — run: git submodule update --init")

        build_dir = Path(self.build_temp).resolve() / "libmagic"
        build_dir.mkdir(parents=True, exist_ok=True)

        if not (FILE_SRC / "configure").exists():
            subprocess.check_call(["autoreconf", "-fi"], cwd=FILE_SRC)
        if not (build_dir / "Makefile").exists():
            subprocess.check_call([str(FILE_SRC / "configure"), *CONFIGURE_ARGS], cwd=build_dir)

        jobs = str(os.cpu_count() or 1)
        subprocess.check_call(["make", "-C", "src", "-j", jobs], cwd=build_dir)  # libmagic.a + file
        subprocess.check_call(["make", "-C", "magic"], cwd=build_dir)            # magic.mgc

        for ext in self.extensions:
            ext.include_dirs.append(str(build_dir / "src"))         
            ext.extra_objects.append(str(build_dir / "src" / ".libs" / "libmagic.a"))

        super().run()

        # Ship the compiled database next to the extension. libmagic's built-in
        # default path (/usr/local/share/misc/magic) does not exist on a user's
        # machine, so src/py_magic/__init__.py loads this copy explicitly.
        mgc = build_dir / "magic" / "magic.mgc"
        targets = [Path(self.build_lib) / "py_magic"]
        if self.inplace:
            targets.append(HERE / "src" / "py_magic")   # editable installs never touch build_lib
        for dest in targets:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy(mgc, dest / "magic.mgc")

setup(
  version=f"{libmagic_version()}.0",   # -> 5.45.0; everything else lives in pyproject.toml
  packages=["py_magic"],
  package_dir={"": "src"},
  package_data={"py_magic": ["magic.mgc"]},
  ext_modules=[Extension("py_magic._magic", sources=["src/_magic.c"])],
  cmdclass={"build_ext": build_ext_static_magic},
)
