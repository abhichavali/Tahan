"""Compile the optional native rules engine.

Project metadata lives in pyproject.toml; this file exists only to declare the
C++ extension (setuptools still needs a setup.py for that). Building it:

    python3 setup.py build_ext --inplace   # -> hanat/_chess.<ext>.so

is optional — the package runs on a pure-Python fallback when the extension is
absent; the native build just makes move generation ~100x faster.
"""

from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            "hanat._chess",
            ["hanat/_chess.cpp"],
            extra_compile_args=["-O3", "-std=c++17"],
        )
    ],
)
