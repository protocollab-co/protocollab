"""Unit tests for PythonGenerator and LuaGenerator."""

import ast
import importlib.util
import struct
from pathlib import Path

import pytest

from protocollab.generators import GeneratorError, LuaGenerator, PythonGenerator


class TestPythonGeneratorOutput:
    def test_creates_py_file(self, ping_spec, tmp_path):
        paths = PythonGenerator().generate(ping_spec, tmp_path)
        assert len(paths) == 1
        assert paths[0].suffix == ".py"
        assert paths[0].exists()

    def test_output_filename(self, ping_spec, tmp_path):
        paths = PythonGenerator().generate(ping_spec, tmp_path)
        assert paths[0].name == "ping_protocol_parser.py"

    def test_creates_output_dir(self, ping_spec, tmp_path):
        out = tmp_path / "nonexistent" / "deep"
        PythonGenerator().generate(ping_spec, out)
        assert out.exists()

    def test_file_not_empty(self, ping_spec, tmp_path):
        paths = PythonGenerator().generate(ping_spec, tmp_path)
        assert paths[0].stat().st_size > 0


class TestPythonGeneratorContent:
    def test_valid_python_syntax(self, ping_spec, tmp_path):
        source = PythonGenerator().generate(ping_spec, tmp_path)[0].read_text(encoding="utf-8")
        ast.parse(source)

    def test_contains_core_methods_and_fields(self, ping_spec, tmp_path):
        src = PythonGenerator().generate(ping_spec, tmp_path)[0].read_text()
        assert "class PingProtocol" in src
        assert "def parse(" in src
        assert "def serialize(" in src
        assert "type_id" in src
        assert "sequence_number" in src
        assert "payload_size" in src

    def test_endian_format_markers(self, ping_spec, be_spec, tmp_path):
        le_src = PythonGenerator().generate(ping_spec, tmp_path)[0].read_text()
        be_src = PythonGenerator().generate(be_spec, tmp_path)[0].read_text()
        assert '_FORMAT: ClassVar[str] = "<' in le_src
        assert '_FORMAT: ClassVar[str] = ">' in be_src

    def test_empty_seq_valid_syntax(self, empty_seq_spec, tmp_path):
        src = PythonGenerator().generate(empty_seq_spec, tmp_path)[0].read_text(encoding="utf-8")
        ast.parse(src)

    def test_all_int_types(self, tmp_path):
        for type_name in ["u1", "u2", "u3", "u4", "u8", "s1", "s2", "s4", "s8"]:
            spec = {"meta": {"id": "t_proto", "endian": "le"}, "seq": [{"id": "x", "type": type_name}]}
            src = PythonGenerator().generate(spec, tmp_path)[0].read_text(encoding="utf-8")
            ast.parse(src)


class TestPythonGeneratorFunctional:
    def _import_module(self, path: Path):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    def test_parse_correct_bytes(self, ping_spec, tmp_path):
        module = self._import_module(PythonGenerator().generate(ping_spec, tmp_path)[0])
        cls = module.PingProtocol
        data = struct.pack("<B", 1) + struct.pack("<I", 12345) + struct.pack("<H", 64)
        obj = cls.parse(data)
        assert obj.type_id == 1
        assert obj.sequence_number == 12345
        assert obj.payload_size == 64

    def test_serialize_round_trip(self, ping_spec, tmp_path):
        module = self._import_module(PythonGenerator().generate(ping_spec, tmp_path)[0])
        cls = module.PingProtocol
        data = struct.pack("<B", 7) + struct.pack("<I", 99) + struct.pack("<H", 256)
        assert cls.parse(data).serialize() == data

    def test_parse_raises_on_short_data(self, ping_spec, tmp_path):
        module = self._import_module(PythonGenerator().generate(ping_spec, tmp_path)[0])
        with pytest.raises(ValueError, match="Not enough data"):
            module.PingProtocol.parse(b"\x01\x02")

    def test_big_endian_parse(self, be_spec, tmp_path):
        module = self._import_module(PythonGenerator().generate(be_spec, tmp_path)[0])
        obj = module.BeProto.parse(struct.pack(">H", 0x0800))
        assert obj.value == 0x0800

    def test_u3_big_endian_round_trip(self, tmp_path):
        spec = {"meta": {"id": "u3_be", "endian": "be"}, "seq": [{"id": "value", "type": "u3"}]}
        module = self._import_module(PythonGenerator().generate(spec, tmp_path)[0])
        cls = module.U3Be
        raw = bytes([0x01, 0x02, 0x03])
        obj = cls.parse(raw)
        assert obj.value == 0x010203
        assert obj.serialize() == raw

    def test_u3_little_endian_round_trip(self, tmp_path):
        spec = {"meta": {"id": "u3_le", "endian": "le"}, "seq": [{"id": "value", "type": "u3"}]}
        module = self._import_module(PythonGenerator().generate(spec, tmp_path)[0])
        cls = module.U3Le
        raw = bytes([0x03, 0x02, 0x01])
        obj = cls.parse(raw)
        assert obj.value == 0x010203
        assert obj.serialize() == raw


class TestLuaGeneratorOutput:
    def test_creates_lua_file(self, ping_spec, tmp_path):
        paths = LuaGenerator().generate(ping_spec, tmp_path)
        assert len(paths) == 1
        assert paths[0].suffix == ".lua"
        assert paths[0].exists()

    def test_output_filename(self, ping_spec, tmp_path):
        paths = LuaGenerator().generate(ping_spec, tmp_path)
        assert paths[0].name == "ping_protocol.lua"

    def test_creates_output_dir(self, ping_spec, tmp_path):
        out = tmp_path / "lua_out"
        LuaGenerator().generate(ping_spec, out)
        assert out.exists()


class TestLuaGeneratorContent:
    def test_basic_lua_content(self, ping_spec, tmp_path):
        src = LuaGenerator().generate(ping_spec, tmp_path)[0].read_text()
        assert 'Proto("ping_protocol"' in src
        assert "dissector" in src
        assert "ProtoField" in src
        assert "f_type_id" in src
        assert "f_sequence_number" in src
        assert "PING_PROTOCOL" in src

    def test_empty_seq(self, empty_seq_spec, tmp_path):
        assert LuaGenerator().generate(empty_seq_spec, tmp_path)[0].exists()

    def test_all_int_types_lua(self, tmp_path):
        for type_name in ["u1", "u2", "u3", "u4", "u8", "s1", "s2", "s4", "s8"]:
            spec = {"meta": {"id": "t_proto", "endian": "le"}, "seq": [{"id": "x", "type": type_name}]}
            assert LuaGenerator().generate(spec, tmp_path)[0].exists()

    def test_u3_lua_field_uses_explicit_value_add(self, tmp_path):
        spec = {"meta": {"id": "u3_proto", "endian": "be"}, "seq": [{"id": "x", "type": "u3"}]}
        src = LuaGenerator().generate(spec, tmp_path)[0].read_text()
        assert "ProtoField.uint24" in src
        assert "subtree:add(f_x, range, value_x)" in src

    def test_u3_lua_little_endian_manual_assembly(self, tmp_path):
        spec = {"meta": {"id": "u3_le_proto", "endian": "le"}, "seq": [{"id": "x", "type": "u3"}]}
        src = LuaGenerator().generate(spec, tmp_path)[0].read_text()
        assert "bit32.lshift((buffer(offset + 1, 1):uint()), 8)" in src
        assert "bit32.lshift((buffer(offset + 2, 1):uint()), 16)" in src

    def test_supports_expression_backed_wireshark_fields(self, ping_spec_with_instances, tmp_path):
        src = LuaGenerator().generate(ping_spec_with_instances, tmp_path)[0].read_text()
        assert 'ProtoField.bool("ping_protocol.lan", "LAN")' in src
        assert 'ProtoField.string("ping_protocol.scope", "Scope")' in src
        assert "local value_lan = " in src
        assert "local value_scope = " in src

    def test_filter_only_and_string_virtual_fields(self, ping_spec_with_instances, tmp_path):
        src = LuaGenerator().generate(ping_spec_with_instances, tmp_path)[0].read_text()
        assert "if value_lan then" in src
        assert "subtree:add(f_inst_lan, buffer(0, 0), true)" in src
        assert "subtree:add(f_inst_scope, buffer(0, 0), value_scope)" in src

    def test_instances_dependency_order(self, ping_spec_with_reordered_instances, tmp_path):
        src = LuaGenerator().generate(ping_spec_with_reordered_instances, tmp_path)[0].read_text()
        assert src.index("local value_lan =") < src.index("local value_scope =")

    def test_ternary_compiles_without_and_or_fallthrough(self, tmp_path):
        spec = {
            "meta": {"id": "quoted_proto", "endian": "le", "title": "Quoted Proto"},
            "seq": [{"id": "src_ip", "type": "u4"}],
            "instances": {
                "lan": {
                    "value": "false if src_ip == 1 else true",
                    "wireshark": {"type": "bool", "label": "LAN"},
                }
            },
        }
        src = LuaGenerator().generate(spec, tmp_path)[0].read_text()
        assert "(function() if" in src
        assert "and (false) or" not in src

    def test_safe_lua_string_literals(self, tmp_path):
        spec = {
            "meta": {"id": "quoted_proto", "endian": "le", "title": 'Ping "Локал"'},
            "seq": [{"id": "src_ip", "type": "u4"}],
            "instances": {
                "scope": {
                    "value": '"лан"',
                    "wireshark": {"type": "string", "label": 'LAN "локал"'},
                }
            },
        }
        src = LuaGenerator().generate(spec, tmp_path)[0].read_text(encoding="utf-8")
        assert 'Proto("quoted_proto", "Ping \\"Локал\\"")' in src
        assert 'ProtoField.string("quoted_proto.scope", "LAN \\"локал\\"")' in src
        assert "\\u041b" not in src

    def test_in_operator_compiles_to_contains_call(self, tmp_path):
        spec = {
            "meta": {"id": "expr_proto", "endian": "le"},
            "seq": [{"id": "type_id", "type": "u1"}],
            "instances": {
                "is_known": {
                    "value": "type_id in [1, 2, 3]",
                    "wireshark": {"type": "bool", "label": "Is Known"},
                }
            },
        }
        src = LuaGenerator().generate(spec, tmp_path)[0].read_text()
        assert "local function _contains(tbl, value)" in src
        assert "local value_is_known = (_contains({1, 2, 3}, value_type_id))" in src

    def test_list_and_dict_literals_compile_to_lua_tables(self, tmp_path):
        spec = {
            "meta": {"id": "expr_proto", "endian": "le"},
            "seq": [{"id": "type_id", "type": "u1"}],
            "instances": {
                "list_value": {
                    "value": "[1, type_id, 3]",
                    "wireshark": {"type": "string", "label": "List Value"},
                },
                "dict_value": {
                    "value": '{"count": type_id, "fixed": 7}',
                    "wireshark": {"type": "string", "label": "Dict Value"},
                },
            },
        }
        src = LuaGenerator().generate(spec, tmp_path)[0].read_text()
        assert "local value_list_value = {1, value_type_id, 3}" in src
        assert "local value_dict_value = {count=value_type_id, fixed=7}" in src

    def test_comprehension_and_match_compile_to_iife(self, tmp_path):
        spec = {
            "meta": {"id": "expr_proto", "endian": "le"},
            "seq": [{"id": "type_id", "type": "u1"}],
            "instances": {
                "has_large": {
                    "value": "any(x > 2 for x in [1, type_id, 3])",
                    "wireshark": {"type": "bool", "label": "Has Large"},
                },
                "class_name": {
                    "value": 'match type_id with 1 -> "one" | _ -> "other"',
                    "wireshark": {"type": "string", "label": "Class Name"},
                },
            },
        }
        src = LuaGenerator().generate(spec, tmp_path)[0].read_text()
        assert "local value_has_large = (function()" in src
        assert "for _, value_x in ipairs({1, value_type_id, 3}) do" in src
        assert "local value_class_name = (function()" in src
        assert "if (value_type_id) == (1) then return (\"one\")" in src
        assert "elseif true then return (\"other\")" in src


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
        spec = {"meta": {"id": "p", "endian": "le"}, "seq": [{"id": "name", "type": "str", "size": 8}]}
        src = PythonGenerator().generate(spec, tmp_path)[0].read_text()
        ast.parse(src)
        assert "8s" in src

    def test_invalid_filter_only_type_raises(self, tmp_path):
        spec = {
            "meta": {"id": "bad_proto", "endian": "le"},
            "seq": [{"id": "src_ip", "type": "u4"}],
            "instances": {
                "lan": {
                    "value": "src_ip == 1",
                    "wireshark": {"type": "bool", "filter-only": "false"},
                }
            },
        }
        with pytest.raises(GeneratorError, match="filter-only must be a boolean"):
            LuaGenerator().generate(spec, tmp_path)

    def test_invalid_instance_expression_is_wrapped(self, tmp_path):
        spec = {
            "meta": {"id": "bad_proto", "endian": "le"},
            "seq": [{"id": "src_ip", "type": "u4"}],
            "instances": {
                "scope": {
                    "value": "@bad",
                    "wireshark": {"type": "string", "label": "Scope"},
                }
            },
        }
        with pytest.raises(GeneratorError, match=r"instances\.scope\.value"):
            LuaGenerator().generate(spec, tmp_path)

    def test_instance_id_collision_with_seq_field_raises(self, tmp_path):
        spec = {
            "meta": {"id": "bad_proto", "endian": "le"},
            "seq": [{"id": "scope", "type": "u4"}],
            "instances": {
                "scope": {
                    "value": '"lan"',
                    "wireshark": {"type": "string", "label": "Scope"},
                }
            },
        }
        with pytest.raises(GeneratorError, match="collides with a seq field id"):
            LuaGenerator().generate(spec, tmp_path)

    def test_cyclic_instance_dependencies_raise(self, tmp_path):
        spec = {
            "meta": {"id": "bad_proto", "endian": "le"},
            "seq": [{"id": "src_ip", "type": "u4"}],
            "instances": {
                "a": {
                    "value": '"x" if b else "y"',
                    "wireshark": {"type": "string", "label": "A"},
                },
                "b": {
                    "value": '"x" if a else "y"',
                    "wireshark": {"type": "string", "label": "B"},
                },
            },
        }
        with pytest.raises(GeneratorError, match="Cyclic dependency"):
            LuaGenerator().generate(spec, tmp_path)

    def test_unknown_instance_dependency_raises(self, tmp_path):
        spec = {
            "meta": {"id": "bad_proto", "endian": "le"},
            "seq": [{"id": "src_ip", "type": "u4"}],
            "instances": {
                "scope": {
                    "value": '"lan" if missing_scope else "inet"',
                    "wireshark": {"type": "string", "label": "Scope"},
                }
            },
        }
        with pytest.raises(GeneratorError, match=r"Unknown name\(s\) in instances.scope.value"):
            LuaGenerator().generate(spec, tmp_path)

    def test_invalid_wireshark_instance_type_raises(self, tmp_path):
        spec = {
            "meta": {"id": "bad_proto", "endian": "le"},
            "seq": [{"id": "src_ip", "type": "u4"}],
            "instances": {
                "scope": {
                    "value": '"lan"',
                    "wireshark": {"type": "number"},
                }
            },
        }
        with pytest.raises(GeneratorError, match="wireshark.type"):
            LuaGenerator().generate(spec, tmp_path)
