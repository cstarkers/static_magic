import os, re, shutil, subprocess, time
from pathlib import Path
from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext
from setuptools.command.sdist import sdist

HERE = Path(__file__).parent.resolve()
FILE_SRC = HERE / "third_party" / "file"

# The third part of the version: bump for a bindings-only release, reset to 0
# when the libmagic submodule moves to a new release. See README, "Upgrading libmagic".
BINDING_REVISION = 0

CONFIGURE_ARGS = [
  "--disable-shared", "--enable-static", "--with-pic",
  "--disable-zlib", "--disable-bzlib", "--disable-xzlib",
  "--disable-zstdlib", "--disable-lzlib", "--disable-libseccomp",
  "--disable-dependency-tracking",
]

def libmagic_version():
  text = (FILE_SRC / "configure.ac").read_text()
  return re.search(r"AC_INIT\(\[file\],\[([^\]]+)\]", text).group(1)


def check_thread_safe_locale(config_h):
    # libmagic's regex code switches to the C locale around each match. With
    # newlocale/uselocale/freelocale it does that per thread; without them it
    # falls back to setlocale(), which is process-wide and races with every
    # other thread. static_magic promises thread safety, so refuse to build that.
    defined = set(re.findall(r"^#define (HAVE_\w+) 1$", config_h.read_text(), re.M))
    missing = {"HAVE_NEWLOCALE", "HAVE_USELOCALE", "HAVE_FREELOCALE"} - defined
    if missing:
        raise SystemExit(
            f"libmagic's configure did not find {', '.join(sorted(missing))} on this platform; "
            "it would switch locales process-wide, which is not thread-safe."
        )


def ensure_configure():
    # A git checkout of file has no configure script; generating one needs
    # autotools. sdists ship it pre-generated, so installing from one doesn't.
    if not (FILE_SRC / "configure.ac").exists():
        raise SystemExit("third_party/file is empty — run: git submodule update --init")
    if not (FILE_SRC / "configure").exists():
        subprocess.check_call(["autoreconf", "-fi"], cwd=FILE_SRC)
    if (HERE / "PKG-INFO").exists():
        freshen_generated_autotools_files()


def freshen_generated_autotools_files():
    # libmagic's Makefiles regenerate configure & co. with autotools whenever
    # they look older than configure.ac. Some sdist unpackers (uv, for one)
    # don't preserve mtimes, which makes that comparison arbitrary. Give every
    # generated file one timestamp from after the unpack, so none looks stale.
    # Only done for sdists: in a git checkout, stale really does mean stale.
    now = time.time()
    generated = ["aclocal.m4", "configure", "config.h.in", *FILE_SRC.glob("**/Makefile.in")]
    for path in generated:
        os.utime(FILE_SRC / path, (now, now))


class sdist_with_configure(sdist):
    def run(self):
        ensure_configure()   # before the file list is built, so configure is in it
        super().run()


class build_ext_static_magic(build_ext):
    def run(self):
        ensure_configure()

        build_dir = Path(self.build_temp).resolve() / "libmagic"
        build_dir.mkdir(parents=True, exist_ok=True)

        if not (build_dir / "Makefile").exists():
            subprocess.check_call([str(FILE_SRC / "configure"), *CONFIGURE_ARGS], cwd=build_dir)
        check_thread_safe_locale(build_dir / "config.h")

        jobs = str(os.cpu_count() or 1)
        subprocess.check_call(["make", "-C", "src", "-j", jobs], cwd=build_dir)  # libmagic.a + file
        subprocess.check_call(["make", "-C", "magic"], cwd=build_dir)            # magic.mgc

        for ext in self.extensions:
            ext.include_dirs.append(str(build_dir / "src"))         
            ext.extra_objects.append(str(build_dir / "src" / ".libs" / "libmagic.a"))

        super().run()

        # Ship the compiled database next to the extension. libmagic's built-in
        # default path (/usr/local/share/misc/magic) does not exist on a user's
        # machine, so src/static_magic/__init__.py loads this copy explicitly.
        mgc = build_dir / "magic" / "magic.mgc"
        targets = [Path(self.build_lib) / "static_magic"]
        if self.inplace:
            targets.append(HERE / "src" / "static_magic")   # editable installs never touch build_lib
        for dest in targets:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy(mgc, dest / "magic.mgc")

setup(
  version=f"{libmagic_version()}.{BINDING_REVISION}",   # -> 5.45.0; everything else lives in pyproject.toml
  packages=["static_magic"],
  package_dir={"": "src"},
  package_data={"static_magic": ["magic.mgc", "py.typed", "_magic.pyi"]},
  ext_modules=[Extension("static_magic._magic", sources=["src/_magic.c"])],
  cmdclass={"build_ext": build_ext_static_magic, "sdist": sdist_with_configure},
)
