from setuptools import Extension, setup
setup(ext_modules=[Extension("neutral_native._core", ["native.c"])])
