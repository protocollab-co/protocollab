"""Legacy setuptools shim.

Project metadata and dependencies are managed in ``pyproject.toml`` via
Poetry. This file is kept only for compatibility with tooling that still
expects ``setup.py`` to exist.
"""

from setuptools import find_packages, setup


setup(
    name="protocollab",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={
        "console_scripts": [
            "pc=protocollab.main:main",
        ],
    },
)