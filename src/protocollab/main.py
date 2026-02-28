"""CLI entry point for ProtocolLab.

Usage examples::

    protocollab load protocol.yaml
    protocollab load protocol.yaml --output-format json
    protocollab load protocol.yaml --no-cache
    protocollab validate protocol.yaml
    protocollab validate protocol.yaml --schema custom.json --strict
"""

import sys

import click

from protocollab.exceptions import FileLoadError, YAMLParseError
from protocollab.loader import load_protocol
from protocollab.utils import check_file_exists, print_data
from protocollab.validator import validate_protocol
from protocollab.generators import generate, GeneratorError


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
def cli() -> None:
    """ProtocolLab — protocol specification analyser."""


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
    try:
        check_file_exists(file)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    config: dict = {}
    if max_depth is not None:
        config["max_struct_depth"] = max_depth
    if max_imports is not None:
        config["max_imports"] = max_imports
    if max_include_depth is not None:
        config["max_include_depth"] = max_include_depth
    if max_file_size is not None:
        config["max_file_size"] = max_file_size

    try:
        data = load_protocol(file, config=config or None, use_cache=not no_cache)
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
    help="Use the strict ProtocolLab schema (protocol.schema.json).",
)
def validate(file: str, schema, strict: bool) -> None:
    """Validate a protocol YAML file against the ProtocolLab schema."""
    from pathlib import Path as _Path

    try:
        check_file_exists(file)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    schema_path = schema
    if schema_path is None and strict:
        schema_path = str(
            _Path(__file__).parent / "validator" / "schemas" / "protocol.schema.json"
        )

    try:
        result = validate_protocol(file, schema_path=schema_path)
    except FileLoadError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except YAMLParseError as exc:
        click.echo(f"YAML error: {exc}", err=True)
        sys.exit(2)

    if result.is_valid:
        click.echo(f"Valid: {file}")
    else:
        click.echo(
            f"Validation failed: {file} ({len(result.errors)} error(s))", err=True
        )
        for i, err in enumerate(result.errors, 1):
            click.echo(f"  [{i}] {err.path}: {err.message}", err=True)
        sys.exit(3)


# ---------------------------------------------------------------------------
# generate command group
# ---------------------------------------------------------------------------

@cli.group()
def generate_cmd() -> None:
    """Generate parsers and dissectors from a protocol specification."""


cli.add_command(generate_cmd, name="generate")


def _run_generate(file: str, target: str, output: str) -> None:
    """Shared implementation for generate sub-commands."""
    try:
        check_file_exists(file)
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    try:
        from protocollab.loader import load_protocol
        spec = load_protocol(file)
    except FileLoadError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except YAMLParseError as exc:
        click.echo(f"YAML error: {exc}", err=True)
        sys.exit(2)

    try:
        from pathlib import Path as _Path
        paths = generate(spec, target=target, output_dir=output)
    except GeneratorError as exc:
        click.echo(f"Generation error: {exc}", err=True)
        sys.exit(4)

    for p in paths:
        click.echo(f"Generated: {p}")


@generate_cmd.command(name="python")
@click.argument("file", type=click.Path())
@click.option("--output", "-o", type=click.Path(), default="./build", show_default=True)
def generate_python(file: str, output: str) -> None:
    """Generate a Python dataclass parser."""
    _run_generate(file, target="python", output=output)


@generate_cmd.command(name="wireshark")
@click.argument("file", type=click.Path())
@click.option("--output", "-o", type=click.Path(), default="./build", show_default=True)
def generate_wireshark(file: str, output: str) -> None:
    """Generate a Wireshark Lua dissector."""
    _run_generate(file, target="wireshark", output=output)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    cli()


if __name__ == "__main__":
    main()
