"""Tests for protocollab.utils — file_utils and yaml_utils."""

import json
import pytest

from protocollab.utils.file_utils import resolve_path, check_file_exists
from protocollab.utils.yaml_utils import to_json, to_yaml, print_data

# ---------------------------------------------------------------------------
# file_utils
# ---------------------------------------------------------------------------


class TestResolvePath:
    def test_absolute_path_unchanged(self, tmp_path):
        f = tmp_path / "proto.yaml"
        f.touch()
        result = resolve_path(str(f))
        assert result == str(f.resolve())

    def test_relative_path_resolved(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        f = tmp_path / "proto.yaml"
        f.touch()
        result = resolve_path("proto.yaml")
        assert result == str(f.resolve())

    def test_returns_string(self, tmp_path):
        f = tmp_path / "x.yaml"
        f.touch()
        assert isinstance(resolve_path(str(f)), str)


class TestCheckFileExists:
    def test_existing_file_does_not_raise(self, tmp_path):
        f = tmp_path / "proto.yaml"
        f.write_text("key: val")
        check_file_exists(str(f))  # must not raise

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError, match="No such file"):
            check_file_exists("/nonexistent/missing.yaml")

    def test_directory_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Not a file"):
            check_file_exists(str(tmp_path))


# ---------------------------------------------------------------------------
# yaml_utils
# ---------------------------------------------------------------------------

DATA = {"version": "1.0", "items": [1, 2, 3], "nested": {"key": "value"}}


class TestToJson:
    def test_produces_valid_json(self):
        result = to_json(DATA)
        parsed = json.loads(result)
        assert parsed == DATA

    def test_indented_by_default(self):
        result = to_json({"a": 1})
        assert "\n" in result  # pretty-printed

    def test_unicode_not_escaped(self):
        result = to_json({"name": "Привет"})
        assert "Привет" in result

    def test_custom_indent(self):
        result = to_json({"a": 1}, indent=4)
        assert "    " in result


class TestToYaml:
    def test_produces_string(self):
        result = to_yaml(DATA)
        assert isinstance(result, str)

    def test_contains_keys(self):
        result = to_yaml(DATA)
        assert "version" in result
        assert "1.0" in result

    def test_roundtrip(self):
        from ruamel.yaml import YAML

        result = to_yaml(DATA)
        y = YAML()
        parsed = y.load(result)
        assert dict(parsed) == DATA


class TestPrintData:
    def test_json_format(self, capsys):
        print_data({"a": 1}, output_format="json")
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed == {"a": 1}

    def test_yaml_format(self, capsys):
        print_data({"key": "value"}, output_format="yaml")
        out = capsys.readouterr().out
        assert "key" in out
        assert "value" in out

    def test_default_format_is_yaml(self, capsys):
        print_data({"x": 42})
        out = capsys.readouterr().out
        assert "x:" in out
        assert "42" in out
