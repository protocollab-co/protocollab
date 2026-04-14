"""Lua / Wireshark dissector generator for `protocollab` protocol specifications."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from protocollab.expression import (
    Attribute,
    BinOp,
    ExpressionSyntaxError,
    Literal,
    Name,
    Subscript,
    Ternary,
    UnaryOp,
    parse_expr,
)
from protocollab.generators.base_generator import BaseGenerator, GeneratorError

# lua_type, size_bytes, optional_base
_LUA_TYPE_MAP: Dict[str, tuple] = {
    "u1": ("uint8", 1, None),
    "u2": ("uint16", 2, "base.DEC"),
    "u3": ("uint24", 3, None),
    "u4": ("uint32", 4, "base.DEC"),
    "u8": ("uint64", 8, "base.DEC"),
    "s1": ("int8", 1, None),
    "s2": ("int16", 2, "base.DEC"),
    "s4": ("int32", 4, "base.DEC"),
    "s8": ("int64", 8, "base.DEC"),
    "str": ("string", None, None),  # requires 'size' in field spec
}

_TEMPLATES_DIR = Path(__file__).parent / "templates" / "lua"
_INSTANCE_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_EXPR_RESERVED_NAMES = {"and", "or", "not", "if", "else", "true", "false"}
_LUA_KEYWORDS = {
    "and",
    "break",
    "do",
    "else",
    "elseif",
    "end",
    "false",
    "for",
    "function",
    "goto",
    "if",
    "in",
    "local",
    "nil",
    "not",
    "or",
    "repeat",
    "return",
    "then",
    "true",
    "until",
    "while",
}


def _lua_string_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _lua_literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _lua_string_literal(value)
    return repr(value)


def _compile_lua_expr(node: Any) -> str:
    if isinstance(node, Literal):
        return _lua_literal(node.value)
    if isinstance(node, Name):
        return f"value_{node.name}"
    if isinstance(node, Attribute):
        return f"({_compile_lua_expr(node.obj)}).{node.attr}"
    if isinstance(node, Subscript):
        return f"({_compile_lua_expr(node.obj)})[{_compile_lua_expr(node.index)}]"
    if isinstance(node, UnaryOp):
        operand = _compile_lua_expr(node.operand)
        if node.op == "-":
            return f"(-({operand}))"
        if node.op == "not":
            return f"(not ({operand}))"
        raise GeneratorError(
            f"Unsupported unary operator {node.op!r} in Lua expression generation."
        )
    if isinstance(node, BinOp):
        left = _compile_lua_expr(node.left)
        right = _compile_lua_expr(node.right)
        if node.op == "!=":
            return f"(({left}) ~= ({right}))"
        if node.op == "//":
            return f"math.floor(({left}) / ({right}))"
        if node.op == "<<":
            return f"bit32.lshift(({left}), ({right}))"
        if node.op == ">>":
            return f"bit32.rshift(({left}), ({right}))"
        if node.op == "&":
            return f"bit32.band(({left}), ({right}))"
        if node.op == "^":
            return f"bit32.bxor(({left}), ({right}))"
        if node.op == "|":
            return f"bit32.bor(({left}), ({right}))"
        return f"(({left}) {node.op} ({right}))"
    if isinstance(node, Ternary):
        condition = _compile_lua_expr(node.condition)
        value_if_true = _compile_lua_expr(node.value_if_true)
        value_if_false = _compile_lua_expr(node.value_if_false)
        return (
            f"(function() if ({condition}) then return ({value_if_true}) "
            f"else return ({value_if_false}) end end)()"
        )

    raise GeneratorError(f"Unsupported AST node {type(node)!r} in Lua expression generation.")


def _collect_name_refs(node: Any) -> set[str]:
    if isinstance(node, Literal):
        return set()
    if isinstance(node, Name):
        return {node.name}
    if isinstance(node, Attribute):
        return _collect_name_refs(node.obj)
    if isinstance(node, Subscript):
        return _collect_name_refs(node.obj) | _collect_name_refs(node.index)
    if isinstance(node, UnaryOp):
        return _collect_name_refs(node.operand)
    if isinstance(node, BinOp):
        return _collect_name_refs(node.left) | _collect_name_refs(node.right)
    if isinstance(node, Ternary):
        return (
            _collect_name_refs(node.condition)
            | _collect_name_refs(node.value_if_true)
            | _collect_name_refs(node.value_if_false)
        )
    raise GeneratorError(f"Unsupported AST node {type(node)!r} in name collection.")


def _validate_instance_id(instance_id: str, field_ids: set[str]) -> None:
    if not _INSTANCE_ID_RE.match(instance_id):
        raise GeneratorError(
            "Wireshark instance "
            f"'{instance_id}' must be a valid identifier: letters, digits, underscore; "
            "cannot start with a digit."
        )
    if instance_id in _EXPR_RESERVED_NAMES:
        raise GeneratorError(
            "Wireshark instance "
            f"'{instance_id}' uses a reserved expression keyword and cannot be referenced safely."
        )
    if instance_id in _LUA_KEYWORDS:
        raise GeneratorError(
            "Wireshark instance "
            f"'{instance_id}' uses a reserved Lua keyword and cannot be generated safely."
        )
    if instance_id in field_ids:
        raise GeneratorError(
            f"Wireshark instance '{instance_id}' collides with a seq field id of the same name."
        )


def _order_instances(instances: list[dict[str, Any]], field_ids: set[str]) -> list[dict[str, Any]]:
    instance_ids = {instance["id"] for instance in instances}
    for instance in instances:
        path = f"instances.{instance['id']}.value"
        referenced_names = _collect_name_refs(instance["ast"])
        unknown_names = sorted(referenced_names - field_ids - instance_ids)
        if unknown_names:
            raise GeneratorError(f"Unknown name(s) in {path}: {', '.join(unknown_names)}.")
        instance["dependencies"] = referenced_names & instance_ids

    ordered: list[dict[str, Any]] = []
    emitted_ids: set[str] = set()
    remaining = list(instances)
    while remaining:
        ready = [
            instance for instance in remaining if instance["dependencies"].issubset(emitted_ids)
        ]
        if not ready:
            cycle_ids = ", ".join(instance["id"] for instance in remaining)
            raise GeneratorError(
                f"Cyclic dependency detected between Wireshark instances: {cycle_ids}."
            )
        for instance in ready:
            ordered.append(instance)
            emitted_ids.add(instance["id"])
            remaining.remove(instance)

    return ordered


def _field_value_expr(spec_type: str, endian: str) -> str:
    if spec_type == "str":
        return "range:string()"
    if spec_type == "u1":
        return "range:uint()"
    if spec_type == "u3":
        if endian == "le":
            return (
                "(bit32.bor("
                "(buffer(offset, 1):uint()), "
                "bit32.lshift((buffer(offset + 1, 1):uint()), 8), "
                "bit32.lshift((buffer(offset + 2, 1):uint()), 16)"
                "))"
            )
        return (
            "(bit32.bor("
            "bit32.lshift((buffer(offset, 1):uint()), 16), "
            "bit32.lshift((buffer(offset + 1, 1):uint()), 8), "
            "(buffer(offset + 2, 1):uint())"
            "))"
        )
    if spec_type == "s1":
        return "range:int()"
    if spec_type in {"u2", "u4"}:
        return "range:le_uint()" if endian == "le" else "range:uint()"
    if spec_type == "u8":
        return "range:le_uint64()" if endian == "le" else "range:uint64()"
    if spec_type in {"s2", "s4"}:
        return "range:le_int()" if endian == "le" else "range:int()"
    if spec_type == "s8":
        return "range:le_int64()" if endian == "le" else "range:int64()"
    raise GeneratorError(f"Unsupported field type {spec_type!r} for Lua value extraction.")


def _uses_little_endian(spec_type: str, endian: str) -> bool:
    return endian == "le" and spec_type not in {"u1", "u3", "s1", "str"}


def _normalize_wireshark_instances(
    spec: Dict[str, Any],
    proto_id: str,
    field_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    instances = spec.get("instances") or {}
    if not isinstance(instances, dict):
        raise GeneratorError("'instances' must be a mapping when used by the Wireshark generator.")

    normalized: list[dict[str, Any]] = []
    for instance_id, instance_def in instances.items():
        if not isinstance(instance_def, dict):
            continue

        _validate_instance_id(instance_id, field_ids)

        value_expr = instance_def.get("value")
        if not isinstance(value_expr, str):
            raise GeneratorError(
                f"Wireshark instance '{instance_id}' requires a string 'value' expression."
            )

        try:
            ast = parse_expr(value_expr)
        except ExpressionSyntaxError as exc:
            raise GeneratorError(
                f"Invalid expression in instances.{instance_id}.value: {exc}"
            ) from exc

        wireshark_def = instance_def.get("wireshark")
        if wireshark_def is not None and not isinstance(wireshark_def, dict):
            raise GeneratorError(
                f"Wireshark instance '{instance_id}' must declare wireshark as a mapping."
            )

        normalized_instance = {
            "id": instance_id,
            "ast": ast,
            "expr": _compile_lua_expr(ast),
            "value_name": f"value_{instance_id}",
            "emit_field": wireshark_def is not None,
        }

        if wireshark_def is not None:
            field_type = wireshark_def.get("type")
            if field_type not in {"bool", "string"}:
                raise GeneratorError(
                    "Wireshark instance "
                    f"'{instance_id}' must declare wireshark.type as 'bool' or 'string'."
                )

            filter_only_raw = wireshark_def.get("filter-only", False)
            if not isinstance(filter_only_raw, bool):
                raise GeneratorError(
                    f"instances.{instance_id}.wireshark.filter-only must be a boolean."
                )
            if filter_only_raw and field_type != "bool":
                raise GeneratorError(
                    f"Wireshark instance '{instance_id}' uses filter-only but is not a bool field."
                )

            label = wireshark_def.get("label") or instance_id.replace("_", " ").title()
            normalized_instance.update(
                {
                    "label": label,
                    "label_lua": _lua_string_literal(label),
                    "lua_type": field_type,
                    "filter_only": filter_only_raw,
                    "field_path_lua": _lua_string_literal(f"{proto_id}.{instance_id}"),
                    "field_var": f"f_inst_{instance_id}",
                }
            )

        normalized.append(normalized_instance)

    ordered_instances = _order_instances(normalized, field_ids)
    emitted_fields = [instance for instance in ordered_instances if instance["emit_field"]]
    return ordered_instances, emitted_fields


class LuaGenerator(BaseGenerator):
    """Generates a Wireshark Lua dissector from a protocol specification."""

    def generate(self, spec: Dict[str, Any], output_dir: Path) -> List[Path]:
        """Generate a ``.lua`` dissector file into *output_dir*.

        Returns
        -------
        List[Path]
            Single-element list with the path of the written ``.lua`` file.
        """
        meta = spec.get("meta", {})
        proto_id: str = meta.get("id", "protocol")
        proto_title: str = meta.get("title", proto_id)
        endian: str = meta.get("endian", "le")

        seq = spec.get("seq") or []
        fields = []
        field_ids: set[str] = set()

        for raw in seq:
            field_id = raw.get("id")
            spec_type = raw.get("type")
            if not field_id or not spec_type:
                continue
            field_ids.add(field_id)

            if spec_type not in _LUA_TYPE_MAP:
                raise GeneratorError(
                    f"Unsupported field type '{spec_type}' for field '{field_id}'. "
                    f"Supported types: {', '.join(sorted(_LUA_TYPE_MAP))}."
                )

            lua_type, size, lua_base = _LUA_TYPE_MAP[spec_type]

            if spec_type == "str":
                size = raw.get("size")
                if size is None:
                    raise GeneratorError(
                        f"Field '{field_id}' of type 'str' requires a 'size' attribute."
                    )

            fields.append(
                {
                    "id": field_id,
                    "spec_type": spec_type,
                    "label": field_id.replace("_", " ").title(),
                    "label_lua": _lua_string_literal(field_id.replace("_", " ").title()),
                    "lua_type": lua_type,
                    "lua_base": lua_base,
                    "size": size,
                    "value_expr": _field_value_expr(spec_type, endian),
                    "use_add_le": _uses_little_endian(spec_type, endian),
                    "needs_explicit_value": spec_type == "u3",
                    "field_path_lua": _lua_string_literal(f"{proto_id}.{field_id}"),
                    "field_var": f"f_{field_id}",
                    "value_name": f"value_{field_id}",
                }
            )

        computed_instances, instance_fields = _normalize_wireshark_instances(
            spec, proto_id, field_ids
        )
        all_fields = fields + instance_fields

        env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), keep_trailing_newline=True)
        template = env.get_template("dissector.lua.j2")

        context = {
            "source_file": str(spec.get("_source_file", "<unknown>")),
            "proto_id": proto_id,
            "proto_id_lua": _lua_string_literal(proto_id),
            "proto_title_lua": _lua_string_literal(proto_title),
            "proto_id_upper": proto_id.upper(),
            "fields": fields,
            "computed_instances": computed_instances,
            "instance_fields": instance_fields,
            "fields_list": ", ".join(field["field_var"] for field in all_fields),
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{proto_id}.lua"
        out_path.write_text(template.render(**context), encoding="utf-8")
        return [out_path]
