from setuptools import setup, find_packages

setup(
    name="protocollab",
    version="0.0.1",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=["ruamel.yaml", "pydantic", "click>=8.0", "jsonschema>=4.0", "jinja2>=3.0"],
    entry_points={
        "console_scripts": [
            "protocollab=protocollab.main:main",
        ],
    },
)