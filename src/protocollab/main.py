"""CLI entry point for `pc`.

Usage examples::

    pc load protocol.yaml
    pc load protocol.yaml --output-format json
    pc load protocol.yaml --no-cache
    pc validate protocol.yaml
    pc validate protocol.yaml --schema custom.json --strict

Module fallback::

    python -m protocollab --help
"""

import sys
from typing import Any

import click

from protocollab.exceptions import FileLoadError, YAMLParseError
from protocollab.loader import load_protocol
from protocollab.utils import check_file_exists, print_data
from protocollab.validator import validate_pipeline
from protocollab.generators import generate, GeneratorError

# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """`pc` — protocol specification analyser."""


# ---------------------------------------------------------------------------
# load command
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("file", type=click.Path())
@click.option(
    "--output-format",
    type=click.Choice(["json", "yaml"]),
    default="yaml",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable in-memory cache; always reload from disk.",
)
@click.option(
    "--max-depth",
    type=int,
    default=None,
    metavar="N",
    help="Maximum YAML nesting depth (default: 50).",
)
@click.option(
    "--max-imports",
    type=int,
    default=None,
    metavar="N",
    help="Maximum number of !include directives (default: 100).",
)
@click.option(
    "--max-include-depth",
    type=int,
    default=None,
    metavar="N",
    help="Maximum !include nesting depth (default: 50).",
)
@click.option(
    "--max-file-size",
    type=int,
    default=None,
    metavar="BYTES",
    help="Maximum file size in bytes (default: 10 MB).",
)
def load(
    file: str,
    output_format: str,
    no_cache: bool,
    max_depth,
    max_imports,
    max_include_depth,
    max_file_size,
) -> None:
    """Load a protocol YAML file and print its resolved contents."""
    _ensure_input_file_exists(file)
    config = _build_load_config(max_depth, max_imports, max_include_depth, max_file_size)

    try:
        data = load_protocol(file, config=config, use_cache=not no_cache)
    except FileLoadError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except YAMLParseError as exc:
        click.echo(f"YAML error: {exc}", err=True)
        sys.exit(2)

    print_data(data, output_format=output_format)


# ---------------------------------------------------------------------------
# validate command
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("file", type=click.Path())
@click.option(
    "--schema",
    type=click.Path(),
    default=None,
    metavar="SCHEMA",
    help="Path to a custom JSON Schema file.",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Use the strict `protocollab` schema (protocol.schema.json).",
)
def validate(file: str, schema, strict: bool) -> None:
    """Validate a protocol YAML file against the `protocollab` schema."""
    from pathlib import Path as _Path

    _ensure_input_file_exists(file)

    schema_path = schema
    if schema_path is None and strict:
        schema_path = str(_Path(__file__).parent / "validator" / "schemas" / "protocol.schema.json")

    try:
        result = validate_pipeline(file, schema_path=schema_path)
    except FileLoadError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except YAMLParseError as exc:
        click.echo(f"YAML error: {exc}", err=True)
        sys.exit(2)

    _print_validation_result(file, result, strict)


# ---------------------------------------------------------------------------
# generate command group
# ---------------------------------------------------------------------------


@cli.group()
def generate_cmd() -> None:
    """Generate parsers and dissectors from a protocol specification."""


cli.add_command(generate_cmd, name="generate")


def _ensure_input_file_exists(file: str) -> None:
    try:
        check_file_exists(file)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


def _build_load_config(
    max_depth: int | None,
    max_imports: int | None,
    max_include_depth: int | None,
    max_file_size: int | None,
) -> dict[str, int] | None:
    config: dict[str, int] = {}
    if max_depth is not None:
        config["max_struct_depth"] = max_depth
    if max_imports is not None:
        config["max_imports"] = max_imports
    if max_include_depth is not None:
        config["max_include_depth"] = max_include_depth
    if max_file_size is not None:
        config["max_file_size"] = max_file_size
    return config or None


def _print_validation_result(file: str, result, strict: bool) -> None:
    if result.is_valid and not result.warnings:
        click.echo(f"Valid: {file}")
        return

    if result.is_valid:
        click.echo(f"Valid: {file} ({len(result.warnings)} warning(s))")
        for i, warning in enumerate(result.warnings, 1):
            click.echo(f"  [W{i}] {warning.path}: {warning.message}")
        return

    click.echo(f"Validation failed: {file} ({len(result.errors)} error(s))", err=True)
    if result.errors:
        click.echo("\n  ERRORS:", err=True)
        for i, err in enumerate(result.errors, 1):
            click.echo(f"    [{i}] {err.path}: {err.message}", err=True)
    if result.warnings:
        click.echo(f"\n  WARNINGS ({len(result.warnings)}):", err=True)
        for i, warning in enumerate(result.warnings, 1):
            click.echo(f"    [W{i}] {warning.path}: {warning.message}", err=True)
    if strict and result.warnings and result.is_valid:
        click.echo("(--strict: treating warnings as errors)", err=True)
    sys.exit(3)


def _load_generate_spec(file: str) -> dict[str, Any]:
    """Load and return a protocol specification for generation commands."""
    _ensure_input_file_exists(file)

    try:
        return load_protocol(file)
    except FileLoadError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except YAMLParseError as exc:
        click.echo(f"YAML error: {exc}", err=True)
        sys.exit(2)


def _generate_targets(spec, targets: tuple[str, ...], output: str) -> None:
    """Generate one or more targets from a loaded protocol specification."""
    try:
        paths = []
        for target in targets:
            paths.extend(generate(spec, target=target, output_dir=output))
    except (GeneratorError, ValueError) as exc:
        click.echo(f"Generation error: {exc}", err=True)
        sys.exit(4)

    for p in paths:
        click.echo(f"Generated: {p}")


def _run_generate(file: str, target: str, output: str) -> None:
    """Shared implementation for single-target generate sub-commands."""
    spec = _load_generate_spec(file)
    _generate_targets(spec, (target,), output)


def _register_generate_command(name: str, target: str, help_text: str) -> None:
    @generate_cmd.command(name=name, help=help_text)
    @click.argument("file", type=click.Path())
    @click.option("--output", "-o", type=click.Path(), default="./build", show_default=True)
    def _command(file: str, output: str) -> None:
        _run_generate(file, target=target, output=output)


_register_generate_command("python", "python", "Generate a Python dataclass parser.")
_register_generate_command("wireshark", "wireshark", "Generate a Wireshark Lua dissector.")


@generate_cmd.command(name="cpp")
@click.argument("file", type=click.Path())
@click.option("--output", "-o", type=click.Path(), default="./build", show_default=True)
def generate_cpp(file: str, output: str) -> None:
    """[Pro Preview] Generate a C++20 parser (header-only)."""
    try:
        from protocollab.generators.cpp_generator import CppGenerator  # noqa: F401
    except ImportError:
        click.echo(
            "C++ generation requires `protocollab` Professional. "
            "The cpp_generator module is not available in this installation.",
            err=True,
        )
        sys.exit(4)
    _run_generate(file, target="cpp", output=output)


_register_generate_command("mock-client", "mock-client", "Generate a mock client and its Python parser.")
_register_generate_command("mock-server", "mock-server", "Generate a mock server and its Python parser.")
_register_generate_command("l2-client", "l2-client", "Generate a Scapy L2 client and its Python parser.")
_register_generate_command("l2-server", "l2-server", "Generate a Scapy L2 server and its Python parser.")
_register_generate_command(
    "l3-client", "l3-client", "Generate a TCP L3 socket client and its Python parser."
)
_register_generate_command(
    "l3-server", "l3-server", "Generate a TCP L3 socket server and its Python parser."
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
