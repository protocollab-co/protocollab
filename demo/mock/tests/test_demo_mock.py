import importlib
import importlib.util
import queue
import sys
from pathlib import Path
from typing import Generator

import pytest

DEMO_MOCK_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = DEMO_MOCK_DIR / "generated"
GENERATED_MODULE_NAMES = (
    "demo",
    "demo_mock_cli",
    "ping_protocol_parser",
    "ping_protocol_mock_client",
    "ping_protocol_mock_server",
)
EXPECTED_GENERATED_FILES = (
    GENERATED_DIR / "ping_protocol_parser.py",
    GENERATED_DIR / "ping_protocol_mock_client.py",
    GENERATED_DIR / "ping_protocol_mock_server.py",
)


def _clear_generated_modules() -> None:
    for module_name in GENERATED_MODULE_NAMES:
        sys.modules.pop(module_name, None)
    importlib.invalidate_caches()


def _load_demo_cli_module():
    module_name = "demo_mock_cli"
    module_path = DEMO_MOCK_DIR / "demo.py"
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
    monkeypatch.syspath_prepend(str(DEMO_MOCK_DIR))
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


def test_imports():
    """Проверяем, что все сгенерированные модули импортируются."""
    from ping_protocol_parser import PingProtocol
    from ping_protocol_mock_client import MockClient
    from ping_protocol_mock_server import MockServer

    assert callable(PingProtocol.parse)
    assert callable(MockClient.send)
    assert callable(MockServer.start)


def test_ping_protocol_serialize_deserialize():
    from ping_protocol_parser import PingProtocol

    original = PingProtocol(type_id=0, sequence_number=123, payload_size=8)
    data = original.serialize()
    parsed = PingProtocol.parse(data)

    assert parsed.type_id == original.type_id
    assert parsed.sequence_number == original.sequence_number
    assert parsed.payload_size == original.payload_size


def test_mock_client_server_interaction():
    from ping_protocol_parser import PingProtocol
    from ping_protocol_mock_client import MockClient
    from ping_protocol_mock_server import MockServer

    client_to_server = queue.Queue()
    server_to_client = queue.Queue()

    def ping_handler(request):
        if request.type_id == 0:
            return PingProtocol(
                type_id=1,
                sequence_number=request.sequence_number,
                payload_size=request.payload_size,
            )
        return request

    server = MockServer(client_to_server, server_to_client, handler=ping_handler)
    server.start()

    try:
        client = MockClient(client_to_server, server_to_client)

        ping = PingProtocol(type_id=0, sequence_number=42, payload_size=16)
        response = client.send_and_receive(ping, timeout=2.0)

        assert response is not None
        assert response.type_id == 1
        assert response.sequence_number == 42
        assert response.payload_size == 16
    finally:
        server.stop(timeout=2.0)


def test_mock_client_timeout():
    from ping_protocol_parser import PingProtocol
    from ping_protocol_mock_client import MockClient

    client_to_server = queue.Queue()
    server_to_client = queue.Queue()
    client = MockClient(client_to_server, server_to_client)

    ping = PingProtocol(type_id=0, sequence_number=1, payload_size=8)
    client.send(ping)
    response = client.receive(timeout=0.5)

    assert response is None


def test_mock_server_default_handler():
    from ping_protocol_parser import PingProtocol
    from ping_protocol_mock_client import MockClient
    from ping_protocol_mock_server import MockServer

    client_to_server = queue.Queue()
    server_to_client = queue.Queue()
    server = MockServer(client_to_server, server_to_client)  # no handler -> echo
    server.start()

    try:
        client = MockClient(client_to_server, server_to_client)

        ping = PingProtocol(type_id=0, sequence_number=42, payload_size=8)
        response = client.send_and_receive(ping, timeout=2.0)

        assert response is not None
        assert response.type_id == 0
        assert response.sequence_number == 42
        assert response.payload_size == 8
    finally:
        server.stop(timeout=2.0)
