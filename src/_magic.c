#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <errno.h>
#include <magic.h> // resolves to the build tree's header: setup.py puts it on -I ahead of /usr/include

static const char _magic_pointer_capsule_name[] = "py_magic._magic.handle";

// MAGIC_ERROR makes libmagic return NULL (and set magic_errno) on I/O errors,
// instead of returning the error message as if it were a successful result.
#define BASE_FLAGS MAGIC_ERROR

static void destroy_magic(PyObject *cap){
    magic_t magic = PyCapsule_GetPointer(cap, _magic_pointer_capsule_name);
    if (magic != NULL)
        magic_close(magic);
}

// PyCapsule_New rejects NULL pointers, so a NULL here always means failure,
// and PyCapsule_GetPointer has already set the exception.
static int convert_capsule(PyObject *obj, void *out){
    magic_t magic = PyCapsule_GetPointer(obj, _magic_pointer_capsule_name);
    if (magic == NULL)
        return 0;
    *(magic_t *)out = magic;
    return 1;
}

// Raise from a failed libmagic query. `target` is attached to OSErrors as the
// filename; pass NULL when there isn't one (e.g. querying a buffer).
static void raise_magic_error(magic_t magic, PyObject *target){
    int err = magic_errno(magic);
    if (err != 0) {
        errno = err;
        PyErr_SetFromErrnoWithFilenameObject(PyExc_OSError, target);
    } else {
        const char *msg = magic_error(magic);
        PyErr_Format(PyExc_RuntimeError, "libmagic: %s", msg ? msg : "unknown error");
    }
}

static int set_query_flags(magic_t magic, int mime){
    if (magic_setflags(magic, BASE_FLAGS | (mime ? MAGIC_MIME_TYPE : 0)) != 0) {
        PyErr_SetString(PyExc_RuntimeError, "magic_setflags failed");
        return -1;
    }
    return 0;
}

// init_magic(db_path: str | bytes | os.PathLike) -> capsule
static PyObject *init_magic(PyObject *Py_UNUSED(self), PyObject *args){
    PyObject *db = NULL, *result = NULL;
    magic_t magic = NULL;

    if (!PyArg_ParseTuple(args, "O&", PyUnicode_FSConverter, &db))
        return NULL;

    magic = magic_open(BASE_FLAGS);
    if (magic == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "magic_open failed");
        goto done;
    }
    if (magic_load(magic, PyBytes_AS_STRING(db)) != 0) {
        raise_magic_error(magic, NULL);
        magic_close(magic);
        goto done;
    }
    result = PyCapsule_New(magic, _magic_pointer_capsule_name, destroy_magic);
    if (result == NULL)
        magic_close(magic);

done:
    Py_DECREF(db);
    return result;
}

// describe_file(magic, path, is_mime) -> str
static PyObject *describe_file(PyObject *Py_UNUSED(self), PyObject *args){
    PyObject *target = NULL, *path = NULL, *result = NULL;
    magic_t magic = NULL;
    int mime = 0;
    const char *description;

    // Keep the original object around so OSError can report the filename as given.
    if (!PyArg_ParseTuple(args, "O&Op", convert_capsule, &magic, &target, &mime))
        return NULL;
    if (!PyUnicode_FSConverter(target, &path))
        return NULL;

    if (set_query_flags(magic, mime) != 0)
        goto done;

    Py_BEGIN_ALLOW_THREADS
    description = magic_file(magic, PyBytes_AS_STRING(path));
    Py_END_ALLOW_THREADS

    if (description == NULL) {
        raise_magic_error(magic, target);
        goto done;
    }
    result = PyUnicode_FromString(description);

done:
    Py_DECREF(path);
    return result;
}

// describe_bytes(magic, data: bytes-like, is_mime) -> str
static PyObject *describe_bytes(PyObject *Py_UNUSED(self), PyObject *args){
    PyObject *result = NULL;
    magic_t magic = NULL;
    Py_buffer data;
    int mime = 0;
    const char *description;

    if (!PyArg_ParseTuple(args, "O&y*p", convert_capsule, &magic, &data, &mime))
        return NULL;

    if (set_query_flags(magic, mime) != 0)
        goto done;

    Py_BEGIN_ALLOW_THREADS
    description = magic_buffer(magic, data.buf, (size_t)data.len);
    Py_END_ALLOW_THREADS

    if (description == NULL) {
        raise_magic_error(magic, NULL);
        goto done;
    }
    result = PyUnicode_FromString(description);

done:
    PyBuffer_Release(&data);
    return result;
}

// libmagic_version() -> int, e.g. 545 for libmagic 5.45
static PyObject *libmagic_version(PyObject *Py_UNUSED(self), PyObject *Py_UNUSED(ignored)){
    return PyLong_FromLong(magic_version());
}


static PyMethodDef module_methods[] = {
    {"init_magic", init_magic, METH_VARARGS, "Open a libmagic handle and load the given database."},
    {"describe_file", describe_file, METH_VARARGS, "Describe the file at a path, optionally as a MIME type."},
    {"describe_bytes", describe_bytes, METH_VARARGS, "Describe a bytes-like buffer, optionally as a MIME type."},
    {"libmagic_version", libmagic_version, METH_NOARGS, "The version of the statically linked libmagic, e.g. 545."},
    {NULL, NULL, 0, NULL}};

// The module keeps no state of its own: each libmagic handle lives in its
// capsule, and py_magic.Magic serialises access to it. So it is safe both in
// subinterpreters and without the GIL.
static PyModuleDef_Slot module_slots[] = {
    {Py_mod_multiple_interpreters, Py_MOD_PER_INTERPRETER_GIL_SUPPORTED},
#if PY_VERSION_HEX >= 0x030D0000
    {Py_mod_gil, Py_MOD_GIL_NOT_USED},
#endif
    {0, NULL}};

static struct PyModuleDef magic_module = {
        PyModuleDef_HEAD_INIT,
        .m_name = "py_magic._magic",
        .m_doc = "A versioned wrapper on libmagic",
        .m_size = 0,
        .m_methods = module_methods,
        .m_slots = module_slots,
};

PyMODINIT_FUNC PyInit__magic(void) {
    return PyModuleDef_Init(&magic_module);
}
