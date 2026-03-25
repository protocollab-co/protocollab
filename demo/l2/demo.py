#!/usr/bin/env python3
"""Single entry point for the L2 Scapy demo workflow."""

import argparse
import importlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

from protocollab.generators import L2ClientGenerator, L2ServerGenerator, generate
from protocollab.loader import load_protocol

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEMO_L2_DIR = Path(__file__).resolve().parent
GENERATED_DIR = DEMO_L2_DIR / "generated"
SPEC_PATH = PROJECT_ROOT / "examples" / "simple" / "ping_protocol.yaml"
TESTS_DIR = DEMO_L2_DIR / "tests"
ETHER_TYPE = 0x88B5
CLIENT_MAC = "02:00:00:00:00:01"
SERVER_MAC = "02:00:00:00:00:02"
STOP_TIMEOUT = 2.0


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
    """Generate parser, L2 Scapy runtime, and Wireshark artefacts."""
    _clean_generated_dir()
    spec = load_protocol(str(SPEC_PATH))

    steps = [
        (
            "Python parser",
            lambda: generate(spec, target="python", output_dir=GENERATED_DIR),
        ),
        ("L2 client", lambda: L2ClientGenerator().generate(spec, GENERATED_DIR)),
        ("L2 server", lambda: L2ServerGenerator().generate(spec, GENERATED_DIR)),
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
    l2_client = importlib.import_module("ping_protocol_l2_client").L2ScapyClient
    l2_server = importlib.import_module("ping_protocol_l2_server").L2ScapyServer
    return ping_protocol, l2_client, l2_server


def _make_pong_message(ping_protocol, request):
    return ping_protocol(
        type_id=1,
        sequence_number=request.sequence_number,
        payload_size=request.payload_size,
    )


def run_demo(iface: str) -> Any:
    """Run the generated L2 demo and return the parsed response."""
    ping_protocol, l2_client_cls, l2_server_cls = _load_generated_types()

    def ping_handler(request):
        return _make_pong_message(ping_protocol, request)

    server = l2_server_cls(
        iface=iface,
        local_mac=SERVER_MAC,
        ether_type=ETHER_TYPE,
        handler=ping_handler,
        stop_timeout=STOP_TIMEOUT,
    )
    server.start()
    print(f"Server started on interface {iface} for EtherType 0x{ETHER_TYPE:04x}")

    ping = ping_protocol(type_id=0, sequence_number=42, payload_size=8)
    print(f"Client sending ping: {ping}")

    try:
        client = l2_client_cls(
            iface=iface,
            src_mac=CLIENT_MAC,
            dst_mac=SERVER_MAC,
            ether_type=ETHER_TYPE,
            timeout=STOP_TIMEOUT,
        )
        response = client.send_and_receive(ping)

        if server.last_error is not None:
            raise server.last_error

        print(f"Client received pong: {response}")
        return response
    finally:
        server.stop(timeout=STOP_TIMEOUT)
        if server.is_alive():
            print("Warning: server thread is still alive after stop timeout.")
        else:
            print("Server stopped.")


def run_demo_tests(pytest_args: Sequence[str] | None = None) -> None:
    """Run the L2 demo test suite."""
    command = [sys.executable, "-m", "pytest", str(TESTS_DIR)]
    if pytest_args:
        command.extend(pytest_args)
    subprocess.run(command, check=True, cwd=PROJECT_ROOT)


def run_demo_check(iface: str | None = None, pytest_args: Sequence[str] | None = None) -> None:
    """Generate artefacts, optionally run the live demo, and execute demo tests."""
    generate_demo_files()
    if iface is not None:
        run_demo(iface)
    else:
        print("Skipping live L2 demo run. Pass --iface to exercise Scapy on a real interface.")
    run_demo_tests(pytest_args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="L2 Scapy demo workflow entry point.")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("generate", help="Generate L2 demo artefacts.")

    run_parser = subparsers.add_parser("run", help="Run the generated L2 demo.")
    run_parser.add_argument("--iface", required=True, help="Network interface name for Scapy.")
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
        help="Generate artefacts, optionally run the live demo, and execute demo tests.",
    )
    check_parser.add_argument("--iface", default=None, help="Optional Scapy interface name.")
    check_parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Additional arguments forwarded to pytest.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.error("A subcommand is required. Use 'run --iface <name>' or 'check'.")

    command = args.command

    if command == "generate":
        generate_demo_files()
        return

    if command == "run":
        if getattr(args, "generate", False):
            generate_demo_files()
        run_demo(args.iface)
        return

    if command == "tests":
        run_demo_tests(args.pytest_args)
        return

    if command == "check":
        run_demo_check(args.iface, args.pytest_args)
        return

    parser.error(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
