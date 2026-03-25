import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

DEMO_L2_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = DEMO_L2_DIR / "generated"
GENERATED_MODULE_NAMES = (
    "demo_l2_cli",
    "ping_protocol_parser",
    "ping_protocol_l2_client",
    "ping_protocol_l2_server",
)
EXPECTED_GENERATED_FILES = (
    GENERATED_DIR / "ping_protocol_parser.py",
    GENERATED_DIR / "ping_protocol_l2_client.py",
    GENERATED_DIR / "ping_protocol_l2_server.py",
    GENERATED_DIR / "ping_protocol.lua",
)


def _clear_generated_modules() -> None:
    for module_name in GENERATED_MODULE_NAMES:
        sys.modules.pop(module_name, None)
    importlib.invalidate_caches()


def _load_demo_cli_module():
    module_name = "demo_l2_cli"
    module_path = DEMO_L2_DIR / "demo.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load demo module from {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def prepare_demo_imports(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    monkeypatch.syspath_prepend(str(DEMO_L2_DIR))
    monkeypatch.syspath_prepend(str(GENERATED_DIR))
    _clear_generated_modules()
    yield
    _clear_generated_modules()


def _generate_demo_files() -> None:
    demo_cli = _load_demo_cli_module()
    demo_cli.generate_demo_files()


def _demo_files_missing() -> bool:
    return any(not path.exists() for path in EXPECTED_GENERATED_FILES)


def setup_module(module):
    if _demo_files_missing():
        _generate_demo_files()


def test_generated_files_exist():
    for path in EXPECTED_GENERATED_FILES:
        assert path.exists()


def test_ping_protocol_serialize_deserialize():
    from ping_protocol_parser import PingProtocol

    original = PingProtocol(type_id=0, sequence_number=123, payload_size=8)
    data = original.serialize()
    parsed = PingProtocol.parse(data)

    assert parsed.type_id == original.type_id
    assert parsed.sequence_number == original.sequence_number
    assert parsed.payload_size == original.payload_size


def test_run_demo_uses_generated_types_and_iface(monkeypatch):
    demo_cli = _load_demo_cli_module()

    class FakePingProtocol:
        def __init__(self, type_id, sequence_number, payload_size):
            self.type_id = type_id
            self.sequence_number = sequence_number
            self.payload_size = payload_size

        def __repr__(self):
            return (
                "PingProtocol("
                f"type_id={self.type_id}, "
                f"sequence_number={self.sequence_number}, "
                f"payload_size={self.payload_size}"
                ")"
            )

    class FakeClient:
        def __init__(self, iface, src_mac, dst_mac, ether_type, timeout):
            self.iface = iface
            self.src_mac = src_mac
            self.dst_mac = dst_mac
            self.ether_type = ether_type
            self.timeout = timeout

        def send_and_receive(self, msg):
            return FakePingProtocol(1, msg.sequence_number, msg.payload_size)

    class FakeServer:
        def __init__(self, iface, local_mac, ether_type, handler, stop_timeout):
            self.iface = iface
            self.local_mac = local_mac
            self.ether_type = ether_type
            self.handler = handler
            self.stop_timeout = stop_timeout
            self.last_error = None
            self.stopped = False

        def start(self):
            return None

        def stop(self, timeout=None):
            self.stopped = True

        def is_alive(self):
            return False

    monkeypatch.setattr(
        demo_cli,
        "_load_generated_types",
        lambda: (FakePingProtocol, FakeClient, FakeServer),
    )

    response = demo_cli.run_demo("demo-iface")

    assert response.type_id == 1
    assert response.sequence_number == 42
    assert response.payload_size == 8


def test_generate_demo_files_generates_parser_once():
    demo_cli = _load_demo_cli_module()

    with patch.object(
        demo_cli, "load_protocol", wraps=demo_cli.load_protocol
    ) as load_protocol_mock:
        with patch.object(demo_cli, "generate", wraps=demo_cli.generate) as generate_mock:
            with patch.object(
                demo_cli.L2ClientGenerator,
                "generate",
                autospec=True,
                wraps=demo_cli.L2ClientGenerator.generate,
            ) as client_generate_mock:
                with patch.object(
                    demo_cli.L2ServerGenerator,
                    "generate",
                    autospec=True,
                    wraps=demo_cli.L2ServerGenerator.generate,
                ) as server_generate_mock:
                    demo_cli.generate_demo_files()

    assert load_protocol_mock.call_count == 1
    assert [call.kwargs["target"] for call in generate_mock.call_args_list] == [
        "python",
        "wireshark",
    ]
    assert client_generate_mock.call_count == 1
    assert server_generate_mock.call_count == 1


def test_generated_lua_contains_protocol_name():
    source = (GENERATED_DIR / "ping_protocol.lua").read_text(encoding="utf-8")

    assert 'Proto("ping_protocol"' in source
    assert "dissector" in source


def test_check_skips_live_run_without_iface(monkeypatch):
    demo_cli = _load_demo_cli_module()
    calls = []

    monkeypatch.setattr(demo_cli, "generate_demo_files", lambda: calls.append("generate"))
    monkeypatch.setattr(demo_cli, "run_demo", lambda iface: calls.append(("run", iface)))
    monkeypatch.setattr(demo_cli, "run_demo_tests", lambda args=None: calls.append(("tests", args)))

    with patch("builtins.print") as print_mock:
        demo_cli.run_demo_check()

    assert calls == ["generate", ("tests", None)]
    print_mock.assert_any_call(
        "Skipping live L2 demo run. Pass --iface to exercise Scapy on a real interface."
    )
