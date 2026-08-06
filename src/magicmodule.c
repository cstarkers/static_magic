#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <magic.h> // TODO this is hopefully finding the temp build version, not to my system version, but I'm not 100% confident about that

static PyObject * get_magic_number(PyObject *self, PyObject *args) {
    return PyLong_FromLong(32);
}


// get_magic_for_file(db_path, filename, is_mime) -> str
//
// db_path is the magic.mgc shipped inside this package; py_magic/__init__.py
// resolves it and passes it in, so the C side never has to guess where it is.
// is_mime is a bool, indicating whether to return a mimetype or a normal magic description
static PyObject * get_magic_for_file(PyObject *self, PyObject *args){
    PyObject *db = NULL, *path = NULL, *result = NULL;
    int mime = 0;
    magic_t magic = NULL;
    const char *mime_type;

    if (!PyArg_ParseTuple(args, "O&O&p",
                          PyUnicode_FSConverter, &db,
                          PyUnicode_FSConverter, &path,
                          &mime))
        return NULL;

    int FLAGS = MAGIC_NONE;

    if (mime){
        FLAGS |= MAGIC_MIME_TYPE;
    }

    magic = magic_open(FLAGS);
    if (magic == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "magic_open failed");
        goto done;
    }
    if (magic_load(magic, PyBytes_AS_STRING(db)) != 0) {
        PyErr_Format(PyExc_RuntimeError, "magic_load: %s", magic_error(magic));
        goto done;
    }
    mime_type = magic_file(magic, PyBytes_AS_STRING(path));
    if (mime_type == NULL) {
        PyErr_Format(PyExc_RuntimeError, "magic_file: %s", magic_error(magic));
        goto done;
    }
    result = PyUnicode_FromString(mime_type);

done:
    if (magic != NULL)
        magic_close(magic);
    Py_XDECREF(db);
    Py_XDECREF(path);
    return result;
}


static PyMethodDef module_methods[] = {
    {"get_magic_number", get_magic_number, METH_VARARGS, "get the magic numbers."},
    {"get_magic_for_file", get_magic_for_file, METH_VARARGS, "get the magic description of a file."},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef py_magic = {
        PyModuleDef_HEAD_INIT,
        "_magic",
        "A versioned wrapper on magic",
        -1,            /* size of per-interpreter state of the module, or -1 if the module keeps state in global variables. */
        module_methods
};

PyMODINIT_FUNC PyInit__magic(void) {
    return PyModule_Create(&py_magic);
}

