#define PY_SSIZE_T_CLEAN
#include <Python.h>

static PyObject *
get_magic(PyObject *self, PyObject *args)
{
    return PyLong_FromLong(32);
}

static PyMethodDef module_methods[] = {
    {"get_magic", get_magic, METH_VARARGS, "get the magic numbers."},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef py_magic =
    {
        PyModuleDef_HEAD_INIT,
        "py_magic", 
        "A versioned wrapper on magic",
        -1,            /* size of per-interpreter state of the module, or -1 if the module keeps state in global variables. */
        module_methods};

PyMODINIT_FUNC PyInit_py_magic(void)
{
    return PyModule_Create(&py_magic);
}
