#!/usr/bin/env python3
"""Single entry point for the mock demo workflow."""

import argparse
import importlib
import queue
import subprocess
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_MOCK_DIR = Path(__file__).resolve().parent
GENERATED_DIR = DEMO_MOCK_DIR / "generated"
SPEC_PATH = PROJECT_ROOT / "examples" / "simple" / "ping_protocol.yaml"
TESTS_DIR = DEMO_MOCK_DIR / "tests"


def _ensure_generated_dir_on_path() -> None:
    generated_dir = str(GENERATED_DIR)
    if generated_dir not in sys.path:
        sys.path.insert(0, generated_dir)


def _clean_generated_dir() -> None:
    GENERATED_DIR.mkdir(exist_ok=True)
    for path in GENERATED_DIR.glob("*.py"):
        path.unlink()


def generate_demo_files(python_executable: str | None = None) -> None:
    """Generate mock artefacts into ``generated``."""
    python = python_executable or sys.executable
    _clean_generated_dir()

    steps = [
        (
            "mock client",
            [
                python,
                "-m",
                "protocollab",
                "generate",
                "mock-client",
                str(SPEC_PATH),
                "-o",
                str(GENERATED_DIR),
            ],
        ),
        (
            "mock server",
            [
                python,
                "-m",
                "protocollab",
                "generate",
                "mock-server",
                str(SPEC_PATH),
                "-o",
                str(GENERATED_DIR),
            ],
        ),
    ]

    for label, command in steps:
        print(f"Generating {label}...")
        subprocess.run(command, check=True, cwd=PROJECT_ROOT)

    print(f"Generation completed. Files in {GENERATED_DIR}:")
    for path in sorted(GENERATED_DIR.glob("ping*.py")):
        print(path)


def _load_generated_types():
    _ensure_generated_dir_on_path()
    ping_protocol = importlib.import_module("ping_protocol_parser").PingProtocol
    mock_client = importlib.import_module("ping_protocol_mock_client").MockClient
    mock_server = importlib.import_module("ping_protocol_mock_server").MockServer
    return ping_protocol, mock_client, mock_server


def _make_ping_handler(ping_protocol):
    def ping_handler(request):
        if request.type_id == 0:
            return ping_protocol(
                type_id=1,
                sequence_number=request.sequence_number,
                payload_size=request.payload_size,
            )
        return request

    return ping_handler


def run_demo() -> None:
    """Run the generated mock demo."""
    ping_protocol, mock_client, mock_server = _load_generated_types()

    client_to_server = queue.Queue()
    server_to_client = queue.Queue()

    server = mock_server(
        recv_queue=client_to_server,
        send_queue=server_to_client,
        handler=_make_ping_handler(ping_protocol),
    )
    server.start()
    print("Server started, waiting for requests...")

    client = mock_client(
        send_queue=client_to_server,
        recv_queue=server_to_client,
    )

    ping = ping_protocol(type_id=0, sequence_number=42, payload_size=8)
    print(f"Sending ping: {ping}")

    response = client.send_and_receive(ping, timeout=2.0)
    if response:
        print(f"Received pong: {response}")
    else:
        print("Timeout - no response")

    server.stop()
    print("Server stopped.")


def run_demo_tests(pytest_args: Sequence[str] | None = None) -> None:
    """Run the demo test suite."""
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
    parser = argparse.ArgumentParser(description="Mock demo workflow entry point.")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("generate", help="Generate mock demo artefacts.")

    run_parser = subparsers.add_parser("run", help="Run the generated mock demo.")
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
        if args.generate:
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
