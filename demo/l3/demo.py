#!/usr/bin/env python3
"""Single entry point for the L3 TCP demo workflow."""

import argparse
import importlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from protocollab.generators import L3ClientGenerator, L3ServerGenerator, generate
from protocollab.loader import load_protocol

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_L3_DIR = Path(__file__).resolve().parent
GENERATED_DIR = DEMO_L3_DIR / "generated"
SPEC_PATH = PROJECT_ROOT / "examples" / "simple" / "ping_protocol.yaml"
TESTS_DIR = DEMO_L3_DIR / "tests"
HOST = "127.0.0.1"
PORT = 0
SOCKET_TIMEOUT = 2.0


def _ensure_generated_dir_on_path() -> None:
    generated_dir = str(GENERATED_DIR)
    if generated_dir not in sys.path:
        sys.path.insert(0, generated_dir)


def _clean_generated_dir() -> None:
    GENERATED_DIR.mkdir(exist_ok=True)
    for pattern in ("*.py", "*.lua"):
        for path in GENERATED_DIR.glob(pattern):
            path.unlink()
    for path in GENERATED_DIR.iterdir():
        if path.is_dir():
            shutil.rmtree(path)


def generate_demo_files() -> None:
    """Generate parser, L3 socket runtime, and Wireshark artefacts."""
    _clean_generated_dir()
    spec = load_protocol(str(SPEC_PATH))

    steps = [
        (
            "Python parser",
            lambda: generate(spec, target="python", output_dir=GENERATED_DIR),
        ),
        ("L3 client", lambda: L3ClientGenerator().generate(spec, GENERATED_DIR)),
        ("L3 server", lambda: L3ServerGenerator().generate(spec, GENERATED_DIR)),
        (
            "wireshark dissector",
            lambda: generate(spec, target="wireshark", output_dir=GENERATED_DIR),
        ),
    ]

    for label, step in steps:
        print(f"Generating {label}...")
        step()

    print(f"Generation completed. Files in {GENERATED_DIR}:")
    for path in sorted(GENERATED_DIR.iterdir()):
        print(path)


def _load_generated_types():
    _ensure_generated_dir_on_path()
    ping_protocol = importlib.import_module("ping_protocol_parser").PingProtocol
    l3_client = importlib.import_module("ping_protocol_l3_client").L3SocketClient
    l3_server = importlib.import_module("ping_protocol_l3_server").L3SocketServer
    return ping_protocol, l3_client, l3_server


def _make_pong_message(ping_protocol, request):
    return ping_protocol(
        type_id=1,
        sequence_number=request.sequence_number,
        payload_size=request.payload_size,
    )


def run_demo() -> Any:
    """Run the generated TCP L3 demo and return the parsed response."""
    ping_protocol, l3_client_cls, l3_server_cls = _load_generated_types()

    def ping_handler(request):
        return _make_pong_message(ping_protocol, request)

    server = l3_server_cls(HOST, PORT, handler=ping_handler, timeout=SOCKET_TIMEOUT)
    server.start()
    host, port = server.address
    print(f"Server listening on {host}:{port}")

    ping = ping_protocol(type_id=0, sequence_number=42, payload_size=8)
    print(f"Client sending ping: {ping}")

    try:
        client = l3_client_cls(host, port, timeout=SOCKET_TIMEOUT)
        response = client.send_and_receive(ping)

        if server.last_error is not None:
            raise server.last_error

        print(f"Client received pong: {response}")
        return response
    finally:
        server.stop(timeout=SOCKET_TIMEOUT)


def run_demo_tests(pytest_args: Sequence[str] | None = None) -> None:
    """Run the L3 demo test suite."""
    command = [sys.executable, "-m", "pytest", str(TESTS_DIR)]
    if pytest_args:
        command.extend(pytest_args)
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)


def run_demo_check(pytest_args: Sequence[str] | None = None) -> None:
    """Generate artefacts, run the demo, and execute demo tests."""
    generate_demo_files()
    run_demo()
    run_demo_tests(pytest_args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="L3 TCP demo workflow entry point.")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("generate", help="Generate L3 demo artefacts.")

    run_parser = subparsers.add_parser("run", help="Run the generated TCP demo.")
    run_parser.add_argument(
        "--generate",
        action="store_true",
        help="Regenerate artefacts before running the demo.",
    )

    tests_parser = subparsers.add_parser("tests", help="Run the demo test suite.")
    tests_parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments forwarded to pytest.",
    )

    check_parser = subparsers.add_parser(
        "check",
        help="Generate artefacts, run the demo, and execute demo tests.",
    )
    check_parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments forwarded to pytest.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    command = args.command or "run"

    if command == "generate":
        generate_demo_files()
        return

    if command == "run":
        if getattr(args, "generate", False):
            generate_demo_files()
        run_demo()
        return

    if command == "tests":
        run_demo_tests(args.pytest_args)
        return

    if command == "check":
        run_demo_check(args.pytest_args)
        return

    parser.error(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
