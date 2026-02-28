"""CLI entry point for ProtocolLab.

Usage examples::

    protocollab load protocol.yaml
    protocollab load protocol.yaml --output-format json
    protocollab load protocol.yaml --no-cache
    protocollab load protocol.yaml --max-depth 20 --max-imports 50
"""

import argparse
import sys

from protocollab.exceptions import FileLoadError, YAMLParseError
from protocollab.loader import load_protocol
from protocollab.utils import check_file_exists, print_data

# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="protocollab",
        description="ProtocolLab — protocol specification analyser",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # -- load ---------------------------------------------------------------
    load_p = subparsers.add_parser(
        "load",
        help="Load a protocol YAML file and print its resolved contents.",
    )
    load_p.add_argument(
        "file",
        metavar="FILE",
        help="Path to the root protocol YAML file.",
    )
    load_p.add_argument(
        "--output-format",
        choices=["json", "yaml"],
        default="yaml",
        metavar="FORMAT",
        help="Output format: json or yaml (default: yaml).",
    )
    load_p.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable in-memory cache; always reload from disk.",
    )
    # Security / limit overrides
    load_p.add_argument(
        "--max-depth",
        type=int,
        default=None,
        metavar="N",
        help="Maximum YAML nesting depth (default: 50).",
    )
    load_p.add_argument(
        "--max-imports",
        type=int,
        default=None,
        metavar="N",
        help="Maximum number of !include directives (default: 100).",
    )
    load_p.add_argument(
        "--max-include-depth",
        type=int,
        default=None,
        metavar="N",
        help="Maximum !include nesting depth (default: 50).",
    )
    load_p.add_argument(
        "--max-file-size",
        type=int,
        default=None,
        metavar="BYTES",
        help="Maximum file size in bytes (default: 10 MB).",
    )

    return parser


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def _cmd_load(args: argparse.Namespace) -> int:
    """Handle the ``load`` sub-command.  Returns an exit code."""
    try:
        check_file_exists(args.file)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    config: dict = {}
    if args.max_depth is not None:
        config["max_struct_depth"] = args.max_depth
    if args.max_imports is not None:
        config["max_imports"] = args.max_imports
    if args.max_include_depth is not None:
        config["max_include_depth"] = args.max_include_depth
    if args.max_file_size is not None:
        config["max_file_size"] = args.max_file_size

    try:
        data = load_protocol(
            args.file,
            config=config or None,
            use_cache=not args.no_cache,
        )
    except FileLoadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except YAMLParseError as exc:
        print(f"YAML error: {exc}", file=sys.stderr)
        return 2

    print_data(data, output_format=args.output_format)
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "load":
        sys.exit(_cmd_load(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
