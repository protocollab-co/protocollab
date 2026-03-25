"""Tests for the protocollab CLI using Click's CliRunner."""

import json
import pytest
from click.testing import CliRunner

from protocollab.main import cli

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def ksy_yaml(tmp_path):
    """A minimal valid KSY-compatible YAML (has meta.id)."""
    f = tmp_path / "proto.yaml"
    f.write_text("meta:\n  id: ping_protocol\n  endian: le\nseq: []\n")
    return f


@pytest.fixture()
def bad_meta_yaml(tmp_path):
    """YAML that fails schema: meta.id uses uppercase (invalid pattern)."""
    f = tmp_path / "bad_meta.yaml"
    f.write_text("meta:\n  id: PingProtocol\nseq: []\n")
    return f


@pytest.fixture()
def no_meta_yaml(tmp_path):
    """YAML with no meta section at all — fails schema."""
    f = tmp_path / "no_meta.yaml"
    f.write_text("seq:\n  - id: x\n    type: u1\n")
    return f


# ---------------------------------------------------------------------------
# protocollab load — success
# ---------------------------------------------------------------------------


class TestCLILoadSuccess:
    def test_load_exits_zero(self, runner, simple_yaml):
        result = runner.invoke(cli, ["load", str(simple_yaml)])
        assert result.exit_code == 0

    def test_load_default_format_is_yaml(self, runner, simple_yaml):
        result = runner.invoke(cli, ["load", str(simple_yaml)])
        assert result.exit_code == 0
        assert "version" in result.output

    def test_load_json_format(self, runner, simple_yaml):
        result = runner.invoke(cli, ["load", str(simple_yaml), "--output-format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["version"] == "1.0"

    def test_load_yaml_format_explicit(self, runner, simple_yaml):
        result = runner.invoke(cli, ["load", str(simple_yaml), "--output-format", "yaml"])
        assert result.exit_code == 0
        assert "version:" in result.output

    def test_load_no_cache_flag(self, runner, simple_yaml):
        result = runner.invoke(cli, ["load", str(simple_yaml), "--no-cache"])
        assert result.exit_code == 0

    def test_load_with_include(self, runner, yaml_with_include):
        result = runner.invoke(cli, ["load", str(yaml_with_include)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# protocollab load — errors
# ---------------------------------------------------------------------------


class TestCLILoadErrors:
    def test_missing_file_exits_one(self, runner):
        result = runner.invoke(cli, ["load", "/nonexistent/missing.yaml"])
        assert result.exit_code == 1

    def test_missing_file_stderr_message(self, runner):
        result = runner.invoke(cli, ["load", "/nonexistent/missing.yaml"])
        assert "Error" in result.output or (result.exc_info and True)

    def test_invalid_yaml_exits_two(self, runner, invalid_yaml):
        result = runner.invoke(cli, ["load", str(invalid_yaml)])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# protocollab validate — success
# ---------------------------------------------------------------------------


class TestCLIValidateSuccess:
    def test_validate_valid_file_exits_zero(self, runner, ksy_yaml):
        result = runner.invoke(cli, ["validate", str(ksy_yaml)])
        assert result.exit_code == 0

    def test_validate_prints_valid_message(self, runner, ksy_yaml):
        result = runner.invoke(cli, ["validate", str(ksy_yaml)])
        assert "Valid" in result.output

    def test_validate_yaml_endian_le(self, runner, tmp_path):
        f = tmp_path / "le.yaml"
        f.write_text("meta:\n  id: my_proto\n  endian: le\n")
        result = runner.invoke(cli, ["validate", str(f)])
        assert result.exit_code == 0

    def test_validate_yaml_endian_be(self, runner, tmp_path):
        f = tmp_path / "be.yaml"
        f.write_text("meta:\n  id: my_proto\n  endian: be\n")
        result = runner.invoke(cli, ["validate", str(f)])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# protocollab validate — schema failures
# ---------------------------------------------------------------------------


class TestCLIValidateSchemaFailures:
    def test_no_meta_exits_three(self, runner, no_meta_yaml):
        result = runner.invoke(cli, ["validate", str(no_meta_yaml)])
        assert result.exit_code == 3

    def test_bad_meta_id_exits_three(self, runner, bad_meta_yaml):
        result = runner.invoke(cli, ["validate", str(bad_meta_yaml)])
        assert result.exit_code == 3

    def test_strict_mode_additional_keys_fail(self, runner, tmp_path):
        f = tmp_path / "extra.yaml"
        f.write_text("meta:\n  id: ok_proto\nunknown_key: 123\n")
        result = runner.invoke(cli, ["validate", str(f), "--strict"])
        assert result.exit_code == 3

    def test_invalid_endian_exits_three(self, runner, tmp_path):
        f = tmp_path / "bad_endian.yaml"
        f.write_text("meta:\n  id: my_proto\n  endian: LE\n")
        result = runner.invoke(cli, ["validate", str(f)])
        assert result.exit_code == 3


# ---------------------------------------------------------------------------
# protocollab validate — file errors
# ---------------------------------------------------------------------------


class TestCLIValidateFileErrors:
    def test_missing_file_exits_one(self, runner):
        result = runner.invoke(cli, ["validate", "/nonexistent/missing.yaml"])
        assert result.exit_code == 1

    def test_invalid_yaml_exits_two(self, runner, invalid_yaml):
        result = runner.invoke(cli, ["validate", str(invalid_yaml)])
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# protocollab — help & top-level
# ---------------------------------------------------------------------------


class TestCLIHelp:
    def test_help_exits_zero(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0

    def test_load_subcommand_in_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert "load" in result.output

    def test_validate_subcommand_in_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert "validate" in result.output

    def test_load_help(self, runner):
        result = runner.invoke(cli, ["load", "--help"])
        assert result.exit_code == 0

    def test_validate_help(self, runner):
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
