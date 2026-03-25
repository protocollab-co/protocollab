"""Tests for protocollab.generators (Python + Lua)."""

import ast
import struct
import importlib.util
import pytest
from pathlib import Path
from click.testing import CliRunner

from protocollab.generators import generate, PythonGenerator, LuaGenerator, GeneratorError
from protocollab.main import cli

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def ping_spec():
    """Minimal ping protocol spec (little-endian, 3 fields)."""
    return {
        "meta": {"id": "ping_protocol", "endian": "le", "title": "Ping Protocol"},
        "seq": [
            {"id": "type_id", "type": "u1"},
            {"id": "sequence_number", "type": "u4"},
            {"id": "payload_size", "type": "u2"},
        ],
    }


@pytest.fixture()
def be_spec():
    """Big-endian protocol spec."""
    return {
        "meta": {"id": "be_proto", "endian": "be"},
        "seq": [{"id": "value", "type": "u2"}],
    }


@pytest.fixture()
def empty_seq_spec():
    """Protocol with no fields."""
    return {"meta": {"id": "empty_proto", "endian": "le"}, "seq": []}


@pytest.fixture()
def ping_yaml(tmp_path):
    """File path to a ping_protocol.yaml in tmp_path."""
    f = tmp_path / "ping_protocol.yaml"
    f.write_text(
        "meta:\n  id: ping_protocol\n  endian: le\nseq:\n"
        "  - id: type_id\n    type: u1\n"
        "  - id: sequence_number\n    type: u4\n"
        "  - id: payload_size\n    type: u2\n"
    )
    return f


@pytest.fixture()
def runner():
    return CliRunner()


# ---------------------------------------------------------------------------
# PythonGenerator — file output
# ---------------------------------------------------------------------------


class TestPythonGeneratorOutput:
    def test_creates_py_file(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert len(paths) == 1
        assert paths[0].suffix == ".py"
        assert paths[0].exists()

    def test_output_filename(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert paths[0].name == "ping_protocol_parser.py"

    def test_creates_output_dir(self, ping_spec, tmp_path):
        out = tmp_path / "nonexistent" / "deep"
        gen = PythonGenerator()
        gen.generate(ping_spec, out)
        assert out.exists()

    def test_file_not_empty(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert paths[0].stat().st_size > 0


# ---------------------------------------------------------------------------
# PythonGenerator — generated code content
# ---------------------------------------------------------------------------


class TestPythonGeneratorContent:
    def test_valid_python_syntax(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        source = paths[0].read_text(encoding="utf-8")
        ast.parse(source)  # raises SyntaxError if invalid

    def test_contains_class_name(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert "class PingProtocol" in paths[0].read_text()

    def test_contains_parse_method(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert "def parse(" in paths[0].read_text()

    def test_contains_serialize_method(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert "def serialize(" in paths[0].read_text()

    def test_contains_field_names(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        src = paths[0].read_text()
        assert "type_id" in src
        assert "sequence_number" in src
        assert "payload_size" in src

    def test_little_endian_format(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert '"<' in paths[0].read_text()

    def test_big_endian_format(self, be_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(be_spec, tmp_path)
        assert '">' in paths[0].read_text()

    def test_empty_seq_valid_syntax(self, empty_seq_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(empty_seq_spec, tmp_path)
        ast.parse(paths[0].read_text(encoding="utf-8"))

    def test_all_int_types(self, tmp_path):
        for t in ["u1", "u2", "u4", "u8", "s1", "s2", "s4", "s8"]:
            spec = {"meta": {"id": "t_proto", "endian": "le"}, "seq": [{"id": "x", "type": t}]}
            gen = PythonGenerator()
            paths = gen.generate(spec, tmp_path)
            ast.parse(paths[0].read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# PythonGenerator — functional: generated parser actually works
# ---------------------------------------------------------------------------


class TestPythonGeneratorFunctional:
    def _import_module(self, path: Path):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec is not None, f"Could not load spec from {path}"
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None, f"Could not load module from {path}"
        spec.loader.exec_module(mod)
        return mod

    def test_parse_correct_bytes(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        mod = self._import_module(paths[0])
        cls = mod.PingProtocol

        # pack: u1=0x01, u4=12345, u2=64  — all little-endian
        data = struct.pack("<B", 1) + struct.pack("<I", 12345) + struct.pack("<H", 64)
        obj = cls.parse(data)
        assert obj.type_id == 1
        assert obj.sequence_number == 12345
        assert obj.payload_size == 64

    def test_serialize_round_trip(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        mod = self._import_module(paths[0])
        cls = mod.PingProtocol

        data = struct.pack("<B", 7) + struct.pack("<I", 99) + struct.pack("<H", 256)
        obj = cls.parse(data)
        assert obj.serialize() == data

    def test_parse_raises_on_short_data(self, ping_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        mod = self._import_module(paths[0])
        cls = mod.PingProtocol

        with pytest.raises(ValueError, match="Not enough data"):
            cls.parse(b"\x01\x02")

    def test_big_endian_parse(self, be_spec, tmp_path):
        gen = PythonGenerator()
        paths = gen.generate(be_spec, tmp_path)
        mod = self._import_module(paths[0])
        cls = mod.BeProto

        data = struct.pack(">H", 0x0800)
        obj = cls.parse(data)
        assert obj.value == 0x0800


# ---------------------------------------------------------------------------
# LuaGenerator — file output
# ---------------------------------------------------------------------------


class TestLuaGeneratorOutput:
    def test_creates_lua_file(self, ping_spec, tmp_path):
        gen = LuaGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert len(paths) == 1
        assert paths[0].suffix == ".lua"
        assert paths[0].exists()

    def test_output_filename(self, ping_spec, tmp_path):
        gen = LuaGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert paths[0].name == "ping_protocol.lua"

    def test_creates_output_dir(self, ping_spec, tmp_path):
        out = tmp_path / "lua_out"
        gen = LuaGenerator()
        gen.generate(ping_spec, out)
        assert out.exists()


# ---------------------------------------------------------------------------
# LuaGenerator — generated code content
# ---------------------------------------------------------------------------


class TestLuaGeneratorContent:
    def test_contains_proto_definition(self, ping_spec, tmp_path):
        gen = LuaGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert 'Proto("ping_protocol"' in paths[0].read_text()

    def test_contains_dissector_function(self, ping_spec, tmp_path):
        gen = LuaGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert "dissector" in paths[0].read_text()

    def test_contains_proto_fields(self, ping_spec, tmp_path):
        gen = LuaGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        src = paths[0].read_text()
        assert "ProtoField" in src
        assert "f_type_id" in src
        assert "f_sequence_number" in src

    def test_contains_field_labels(self, ping_spec, tmp_path):
        gen = LuaGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        src = paths[0].read_text()
        assert "Type Id" in src or "type_id" in src.lower()

    def test_protocol_upper_in_dissector(self, ping_spec, tmp_path):
        gen = LuaGenerator()
        paths = gen.generate(ping_spec, tmp_path)
        assert "PING_PROTOCOL" in paths[0].read_text()

    def test_empty_seq(self, empty_seq_spec, tmp_path):
        gen = LuaGenerator()
        paths = gen.generate(empty_seq_spec, tmp_path)
        assert paths[0].exists()

    def test_all_int_types_lua(self, tmp_path):
        for t in ["u1", "u2", "u4", "u8", "s1", "s2", "s4", "s8"]:
            spec = {"meta": {"id": "t_proto", "endian": "le"}, "seq": [{"id": "x", "type": t}]}
            gen = LuaGenerator()
            paths = gen.generate(spec, tmp_path)
            assert paths[0].exists()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestGeneratorErrors:
    def test_unknown_type_python(self, tmp_path):
        spec = {"meta": {"id": "p", "endian": "le"}, "seq": [{"id": "x", "type": "bytes"}]}
        with pytest.raises(GeneratorError, match="Unsupported field type"):
            PythonGenerator().generate(spec, tmp_path)

    def test_unknown_type_lua(self, tmp_path):
        spec = {"meta": {"id": "p", "endian": "le"}, "seq": [{"id": "x", "type": "bytes"}]}
        with pytest.raises(GeneratorError, match="Unsupported field type"):
            LuaGenerator().generate(spec, tmp_path)

    def test_str_without_size_python(self, tmp_path):
        spec = {"meta": {"id": "p", "endian": "le"}, "seq": [{"id": "name", "type": "str"}]}
        with pytest.raises(GeneratorError, match="requires a 'size'"):
            PythonGenerator().generate(spec, tmp_path)

    def test_str_without_size_lua(self, tmp_path):
        spec = {"meta": {"id": "p", "endian": "le"}, "seq": [{"id": "name", "type": "str"}]}
        with pytest.raises(GeneratorError, match="requires a 'size'"):
            LuaGenerator().generate(spec, tmp_path)

    def test_str_with_size_python(self, tmp_path):
        spec = {
            "meta": {"id": "p", "endian": "le"},
            "seq": [{"id": "name", "type": "str", "size": 8}],
        }
        paths = PythonGenerator().generate(spec, tmp_path)
        src = paths[0].read_text()
        ast.parse(src)
        assert "8s" in src

    def test_unknown_target_in_generate(self, tmp_path):
        spec = {"meta": {"id": "p"}, "seq": []}
        with pytest.raises(ValueError, match="Unknown target"):
            generate(spec, target="cobol", output_dir=tmp_path)


# ---------------------------------------------------------------------------
# generate() public API
# ---------------------------------------------------------------------------


class TestGenerateAPI:
    def test_generate_python_returns_path(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="python", output_dir=tmp_path)
        assert len(paths) == 1
        assert paths[0].exists()

    def test_generate_wireshark_returns_path(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="wireshark", output_dir=tmp_path)
        assert len(paths) == 1
        assert paths[0].exists()

    def test_generate_str_output_dir(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="python", output_dir=str(tmp_path))
        assert paths[0].exists()

    def test_generate_mock_client_returns_parser_and_mock_paths(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="mock-client", output_dir=tmp_path)

        assert len(paths) == 2
        assert [path.name for path in paths] == [
            "ping_protocol_parser.py",
            "ping_protocol_mock_client.py",
        ]

    def test_generate_mock_server_returns_parser_and_mock_paths(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="mock-server", output_dir=tmp_path)

        assert len(paths) == 2
        assert [path.name for path in paths] == [
            "ping_protocol_parser.py",
            "ping_protocol_mock_server.py",
        ]


# ---------------------------------------------------------------------------
# CLI: protocollab generate
# ---------------------------------------------------------------------------


class TestCLIGenerate:
    def test_generate_python_exits_zero(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "python", str(ping_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 0

    def test_generate_python_prints_path(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "python", str(ping_yaml), "-o", str(tmp_path)])
        assert "Generated:" in result.output

    def test_generate_wireshark_exits_zero(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "wireshark", str(ping_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 0

    def test_generate_mock_client_also_generates_parser(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(
            cli, ["generate", "mock-client", str(ping_yaml), "-o", str(tmp_path)]
        )

        assert result.exit_code == 0
        assert (tmp_path / "ping_protocol_parser.py").exists()
        assert (tmp_path / "ping_protocol_mock_client.py").exists()
        assert result.output.count("Generated:") == 2

    def test_generate_mock_server_also_generates_parser(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(
            cli, ["generate", "mock-server", str(ping_yaml), "-o", str(tmp_path)]
        )

        assert result.exit_code == 0
        assert (tmp_path / "ping_protocol_parser.py").exists()
        assert (tmp_path / "ping_protocol_mock_server.py").exists()
        assert result.output.count("Generated:") == 2

    def test_generate_missing_file_exits_one(self, runner, tmp_path):
        result = runner.invoke(
            cli, ["generate", "python", "/no/such/file.yaml", "-o", str(tmp_path)]
        )
        assert result.exit_code == 1

    def test_generate_invalid_yaml_exits_two(self, runner, invalid_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "python", str(invalid_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 2

    def test_generate_bad_type_exits_four(self, runner, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("meta:\n  id: p\n  endian: le\nseq:\n  - id: x\n    type: unknown_type\n")
        out = tmp_path / "out"
        result = runner.invoke(cli, ["generate", "python", str(bad), "-o", str(out)])
        assert result.exit_code == 4

    def test_generate_help(self, runner):
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "python" in result.output
        assert "wireshark" in result.output
        assert "mock-client" in result.output
        assert "mock-server" in result.output

    def test_generate_creates_output_dir(self, runner, ping_yaml, tmp_path):
        out = tmp_path / "new_dir"
        runner.invoke(cli, ["generate", "python", str(ping_yaml), "-o", str(out)])
        assert out.exists()
