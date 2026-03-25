import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

DEMO_L3_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = DEMO_L3_DIR / "generated"
GENERATED_MODULE_NAMES = (
    "demo_l3_cli",
    "ping_protocol_parser",
    "ping_protocol_l3_client",
    "ping_protocol_l3_server",
)
EXPECTED_GENERATED_FILES = (
    GENERATED_DIR / "ping_protocol_parser.py",
    GENERATED_DIR / "ping_protocol_l3_client.py",
    GENERATED_DIR / "ping_protocol_l3_server.py",
    GENERATED_DIR / "ping_protocol.lua",
)


def _clear_generated_modules() -> None:
    for module_name in GENERATED_MODULE_NAMES:
        sys.modules.pop(module_name, None)
    importlib.invalidate_caches()


def _load_demo_cli_module():
    module_name = "demo_l3_cli"
    module_path = DEMO_L3_DIR / "demo.py"
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
    monkeypatch.syspath_prepend(str(DEMO_L3_DIR))
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


def test_imports_generated_runtime():
    from ping_protocol_parser import PingProtocol
    from ping_protocol_l3_client import L3SocketClient
    from ping_protocol_l3_server import L3SocketServer

    assert callable(PingProtocol.parse)
    assert callable(PingProtocol.serialize)
    assert callable(L3SocketClient.send_and_receive)
    assert callable(L3SocketServer.start)


def test_ping_protocol_serialize_deserialize():
    from ping_protocol_parser import PingProtocol

    original = PingProtocol(type_id=0, sequence_number=123, payload_size=8)
    data = original.serialize()
    parsed = PingProtocol.parse(data)

    assert parsed.type_id == original.type_id
    assert parsed.sequence_number == original.sequence_number
    assert parsed.payload_size == original.payload_size


def test_tcp_round_trip():
    demo_cli = _load_demo_cli_module()
    response = demo_cli.run_demo()

    assert response.type_id == 1
    assert response.sequence_number == 42
    assert response.payload_size == 8


def test_generated_lua_contains_protocol_name():
    source = (GENERATED_DIR / "ping_protocol.lua").read_text(encoding="utf-8")

    assert 'Proto("ping_protocol"' in source
    assert "dissector" in source


def test_generate_demo_files_generates_parser_once():
    demo_cli = _load_demo_cli_module()

    with patch.object(
        demo_cli, "load_protocol", wraps=demo_cli.load_protocol
    ) as load_protocol_mock:
        with patch.object(demo_cli, "generate", wraps=demo_cli.generate) as generate_mock:
            with patch.object(
                demo_cli.L3ClientGenerator,
                "generate",
                autospec=True,
                wraps=demo_cli.L3ClientGenerator.generate,
            ) as client_generate_mock:
                with patch.object(
                    demo_cli.L3ServerGenerator,
                    "generate",
                    autospec=True,
                    wraps=demo_cli.L3ServerGenerator.generate,
                ) as server_generate_mock:
                    demo_cli.generate_demo_files()

    assert load_protocol_mock.call_count == 1
    assert [call.kwargs["target"] for call in generate_mock.call_args_list] == [
        "python",
        "wireshark",
    ]
    assert client_generate_mock.call_count == 1
    assert server_generate_mock.call_count == 1
