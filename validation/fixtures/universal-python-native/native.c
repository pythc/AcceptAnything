#include <Python.h>
static PyObject *twice(PyObject *self, PyObject *args) {
    long value;
    if (!PyArg_ParseTuple(args, "l", &value)) return NULL;
    return PyLong_FromLong(value * 2);
}
static PyMethodDef methods[] = {{"double", twice, METH_VARARGS, NULL}, {NULL, NULL, 0, NULL}};
static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "_core", NULL, -1, methods};
PyMODINIT_FUNC PyInit__core(void) { return PyModule_Create(&module); }
