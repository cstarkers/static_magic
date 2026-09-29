# static_magic

Yet another set of Python bindings for libmagic, the library behind the `file` command.

There's like 8 of these on PyPI, and even an official one shipped as part of `file`, so why another one?

Well basically none of them statically link and version libmagic. And I want to do that. `static_magic` compiles libmagic into the extension and ships the matching magic database inside the package, so you get the same answers everywhere, whatever libmagic your system has (or doesn't have).

Also I wanted to learn how C extensions work (not CFFI, not Cython, honest-to-god C extensions).

## Install

```
pip install static_magic
```

We use the libmagic version as the first two parts of our version number. So if you install `static_magic==5.45.*` you are guaranteed to get libmagic 5.45. The third part is for changes to the bindings themselves.

Wheels are built for CPython 3.12+ (including free-threaded 3.14t) on:

- Linux x86_64 and aarch64 (glibc / manylinux)
- macOS arm64 (Apple Silicon), macOS 11+

Anywhere else, pip builds from the source distribution, which needs a C compiler and `make`.

## Usage

```python
import static_magic

static_magic.get_description_file("report.pdf")     # 'PDF document, version 1.4, 2 page(s)'
static_magic.get_mime_type_file("report.pdf")       # 'application/pdf'

with open("report.pdf", "rb") as f:
    static_magic.get_mime_type_bytes(f.read(2048))  # 'application/pdf'
```

The module-level functions share a database that's loaded the first time you use one. If you'd rather manage that yourself, or want a custom database, make a `Magic`:

```python
m = static_magic.Magic()                            # or Magic(database="/path/to/magic.mgc")
m.get_description_file("/bin/ls")                   # 'ELF 64-bit LSB pie executable, x86-64, ...'
m.get_description_bytes(b"%PDF-1.4\n")              # 'PDF document, version 1.4'
```

A `Magic` is safe to share between threads; calls on the same instance take turns.

Files that can't be read raise the usual `OSError` subclasses rather than returning libmagic's error text:

```python
try:
    static_magic.get_mime_type_file("missing.txt")
except FileNotFoundError as e:
    print(e.filename)                               # 'missing.txt'
```

`static_magic.libmagic_version()` returns the bundled libmagic version as an int, e.g. `545`.

## Development

libmagic comes from the [`file`](https://github.com/file/file) repository, pinned as a git submodule:

```
git clone --recurse-submodules https://github.com/cstarkers/static_magic.git
cd static_magic
pip install -e .
python -m pytest tests
```

Building from git needs autotools (`autoconf`, `automake`, `libtool`) to generate libmagic's `configure`. Source distributions ship it pre-generated, so installing from PyPI doesn't. After changing the C code, run `pip install -e .` again.

### Upgrading libmagic

The package version comes from the submodule, so moving to a new libmagic is:

1. Check out the new release tag in the submodule, e.g. `git -C third_party/file checkout FILE5_46`.
2. Reset `BINDING_REVISION` in `setup.py` to `0`.
3. `rm -rf build && pip install -e . && python -m pytest tests`. `test_libmagic_version_matches_package_version` checks the compiled libmagic matches the new version.
4. Commit the submodule bump and tag `v5.46.0`.

For a bindings-only release on the same libmagic, bump `BINDING_REVISION` instead.

## License

BSD-2-Clause, see [LICENSE](LICENSE). libmagic's own licence is in [LICENSE-libmagic](LICENSE-libmagic) and is included in every wheel.
