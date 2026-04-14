"""Regression checks for packaged CLI entrypoint names."""

from pathlib import Path
import re


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_poetry_scripts_expose_pc_only() -> None:
    text = (_repo_root() / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r"^pc\s*=\s*\"protocollab\.main:main\"\s*$", text, re.MULTILINE)
    assert not re.search(r"^protocollab\s*=\s*\"protocollab\.main:main\"\s*$", text, re.MULTILINE)


def test_setuptools_console_scripts_expose_pc_only() -> None:
    text = (_repo_root() / "setup.py").read_text(encoding="utf-8")
    assert '"pc=protocollab.main:main"' in text
    assert '"protocollab=protocollab.main:main"' not in text
