import importlib
import importlib.util
import queue
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import patch

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


def test_generated_files_exist():
    for path in EXPECTED_GENERATED_FILES:
        assert path.exists()


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


def test_demo_round_trip():
    demo_cli = _load_demo_cli_module()
    response = demo_cli.run_demo()

    assert response is not None
    assert response.type_id == 1
    assert response.sequence_number == 42
    assert response.payload_size == 8


def test_demo_stop_uses_bounded_timeout_and_warns_if_server_is_still_alive(monkeypatch):
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
        def __init__(self, send_queue, recv_queue):
            self.send_queue = send_queue
            self.recv_queue = recv_queue

        def send_and_receive(self, msg, timeout):
            assert timeout == demo_cli.STOP_TIMEOUT
            return FakePingProtocol(1, msg.sequence_number, msg.payload_size)

    class FakeServer:
        def __init__(self, recv_queue, send_queue, handler):
            self.recv_queue = recv_queue
            self.send_queue = send_queue
            self.handler = handler
            self.stop_timeout = None

        def start(self):
            return None

        def stop(self, timeout=None):
            self.stop_timeout = timeout

        def is_alive(self):
            return True

    fake_server = FakeServer(None, None, None)

    def fake_server_factory(recv_queue, send_queue, handler):
        fake_server.recv_queue = recv_queue
        fake_server.send_queue = send_queue
        fake_server.handler = handler
        return fake_server

    monkeypatch.setattr(
        demo_cli,
        "_load_generated_types",
        lambda: (FakePingProtocol, FakeClient, fake_server_factory),
    )

    with patch("builtins.print") as print_mock:
        response = demo_cli.run_demo()

    assert response is not None
    assert fake_server.stop_timeout == demo_cli.STOP_TIMEOUT
    print_mock.assert_any_call("Warning: server thread is still alive after stop timeout.")


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


def test_generate_demo_files_generates_parser_once():
    demo_cli = _load_demo_cli_module()

    with patch.object(
        demo_cli, "load_protocol", wraps=demo_cli.load_protocol
    ) as load_protocol_mock:
        with patch.object(demo_cli, "generate", wraps=demo_cli.generate) as generate_mock:
            with patch.object(
                demo_cli.MockClientGenerator,
                "generate",
                autospec=True,
                wraps=demo_cli.MockClientGenerator.generate,
            ) as client_generate_mock:
                with patch.object(
                    demo_cli.MockServerGenerator,
                    "generate",
                    autospec=True,
                    wraps=demo_cli.MockServerGenerator.generate,
                ) as server_generate_mock:
                    demo_cli.generate_demo_files()

    assert load_protocol_mock.call_count == 1
    assert [call.kwargs["target"] for call in generate_mock.call_args_list] == [
        "python",
    ]
    assert client_generate_mock.call_count == 1
    assert server_generate_mock.call_count == 1
