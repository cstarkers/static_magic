# yet another set of bindings for libmagic

there's like 8 of these on PyPi, and even an official one shipped as part of `file`, so why another one?

Well basically none of them statically link and version libmagic.  And I want to do that.

Also I wanted to learn how c extensions work (not CFFI, not cython, honest-to-god C extensions).

We use the libmagic version as the first two parts of our version number. So if you install  libmagicpy==5.45.* you are guaranteed to get libmagic==5.45.






