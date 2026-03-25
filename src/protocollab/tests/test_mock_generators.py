import importlib
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Generator

import pytest

from protocollab.generators.mock_client import MockClientGenerator
from protocollab.generators.mock_server import MockServerGenerator
from protocollab.generators.python_generator import PythonGenerator
from protocollab.loader import load_protocol

GENERATED_MODULE_NAMES = (
    "ping_protocol_parser",
    "ping_protocol_mock_client",
    "ping_protocol_mock_server",
)


def _clear_generated_modules() -> None:
    for module_name in GENERATED_MODULE_NAMES:
        sys.modules.pop(module_name, None)
    importlib.invalidate_caches()


def _import_generated_module(module_dir: Path, module_name: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(module_dir))
    return importlib.import_module(module_name)


@pytest.fixture(autouse=True)
def clear_generated_module_cache() -> Generator[None, None, None]:
    _clear_generated_modules()
    yield
    _clear_generated_modules()


@pytest.fixture
def ping_spec():
    """Load ping protocol spec from examples."""
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    file_path = project_root / "examples" / "simple" / "ping_protocol.yaml"
    if not file_path.exists():
        pytest.skip(f"Spec file not found: {file_path}")
    return load_protocol(str(file_path))


def generate_mock_files(spec, output_dir, generator_class):
    """Helper to generate files from a generator."""
    generator = generator_class()
    return generator.generate(spec, output_dir)


def test_mock_client_generation(ping_spec, tmp_path, monkeypatch):
    """Test that mock client generator creates a file and its content is importable."""
    PythonGenerator().generate(ping_spec, tmp_path)

    output_files = generate_mock_files(ping_spec, tmp_path, MockClientGenerator)
    assert len(output_files) == 1
    generated_file = output_files[0]
    assert generated_file.exists()
    assert generated_file.name == "ping_protocol_mock_client.py"

    module = _import_generated_module(tmp_path, "ping_protocol_mock_client", monkeypatch)
    assert hasattr(module, "MockClient")
    mock_client = module.MockClient
    assert callable(getattr(mock_client, "send", None))
    assert callable(getattr(mock_client, "receive", None))
    assert callable(getattr(mock_client, "send_and_receive", None))


def test_mock_server_generation(ping_spec, tmp_path, monkeypatch):
    """Test that mock server generator creates a file and its content is importable."""
    PythonGenerator().generate(ping_spec, tmp_path)

    output_files = generate_mock_files(ping_spec, tmp_path, MockServerGenerator)
    assert len(output_files) == 1
    generated_file = output_files[0]
    assert generated_file.exists()
    assert generated_file.name == "ping_protocol_mock_server.py"

    module = _import_generated_module(tmp_path, "ping_protocol_mock_server", monkeypatch)
    assert hasattr(module, "MockServer")
    mock_server = module.MockServer
    assert callable(getattr(mock_server, "start", None))
    assert callable(getattr(mock_server, "stop", None))


def test_mock_client_server_interaction(ping_spec, tmp_path, monkeypatch):
    """Test full interaction between generated client and server."""
    PythonGenerator().generate(ping_spec, tmp_path)

    generate_mock_files(ping_spec, tmp_path, MockClientGenerator)
    generate_mock_files(ping_spec, tmp_path, MockServerGenerator)

    ping_protocol = _import_generated_module(
        tmp_path, "ping_protocol_parser", monkeypatch
    ).PingProtocol
    mock_client = _import_generated_module(
        tmp_path, "ping_protocol_mock_client", monkeypatch
    ).MockClient
    mock_server = _import_generated_module(
        tmp_path, "ping_protocol_mock_server", monkeypatch
    ).MockServer

    client_to_server = queue.Queue()
    server_to_client = queue.Queue()

    def ping_handler(request):
        if request.type_id == 0:
            return ping_protocol(
                type_id=1,
                sequence_number=request.sequence_number,
                payload_size=request.payload_size,
            )
        return request

    server = mock_server(client_to_server, server_to_client, handler=ping_handler)
    server.start()

    try:
        client = mock_client(client_to_server, server_to_client)

        ping = ping_protocol(type_id=0, sequence_number=123, payload_size=16)
        response = client.send_and_receive(ping, timeout=2.0)

        assert response is not None
        assert response.type_id == 1
        assert response.sequence_number == 123
        assert response.payload_size == 16
    finally:
        server.stop(timeout=2.0)


def test_mock_client_timeout(ping_spec, tmp_path, monkeypatch):
    """Test that client times out when no response arrives."""
    PythonGenerator().generate(ping_spec, tmp_path)

    generate_mock_files(ping_spec, tmp_path, MockClientGenerator)

    ping_protocol = _import_generated_module(
        tmp_path, "ping_protocol_parser", monkeypatch
    ).PingProtocol
    mock_client = _import_generated_module(
        tmp_path, "ping_protocol_mock_client", monkeypatch
    ).MockClient

    client_to_server = queue.Queue()
    server_to_client = queue.Queue()
    client = mock_client(client_to_server, server_to_client)

    ping = ping_protocol(type_id=0, sequence_number=1, payload_size=8)
    client.send(ping)
    response = client.receive(timeout=0.5)

    assert response is None


def test_mock_server_custom_handler(ping_spec, tmp_path, monkeypatch):
    """Test that server uses the provided custom handler."""
    PythonGenerator().generate(ping_spec, tmp_path)

    generate_mock_files(ping_spec, tmp_path, MockClientGenerator)
    generate_mock_files(ping_spec, tmp_path, MockServerGenerator)

    ping_protocol = _import_generated_module(
        tmp_path, "ping_protocol_parser", monkeypatch
    ).PingProtocol
    mock_client = _import_generated_module(
        tmp_path, "ping_protocol_mock_client", monkeypatch
    ).MockClient
    mock_server = _import_generated_module(
        tmp_path, "ping_protocol_mock_server", monkeypatch
    ).MockServer

    def custom_handler(msg):
        return ping_protocol(
            type_id=msg.type_id,
            sequence_number=msg.sequence_number + 1,
            payload_size=msg.payload_size,
        )

    client_to_server = queue.Queue()
    server_to_client = queue.Queue()
    server = mock_server(client_to_server, server_to_client, handler=custom_handler)
    server.start()

    try:
        client = mock_client(client_to_server, server_to_client)

        ping = ping_protocol(type_id=0, sequence_number=100, payload_size=8)
        response = client.send_and_receive(ping, timeout=2.0)

        assert response is not None
        assert response.sequence_number == 101
        assert response.type_id == 0  # unchanged
    finally:
        server.stop(timeout=2.0)


def test_mock_server_default_handler(ping_spec, tmp_path, monkeypatch):
    """Test default echo handler."""
    PythonGenerator().generate(ping_spec, tmp_path)

    generate_mock_files(ping_spec, tmp_path, MockClientGenerator)
    generate_mock_files(ping_spec, tmp_path, MockServerGenerator)

    ping_protocol = _import_generated_module(
        tmp_path, "ping_protocol_parser", monkeypatch
    ).PingProtocol
    mock_client = _import_generated_module(
        tmp_path, "ping_protocol_mock_client", monkeypatch
    ).MockClient
    mock_server = _import_generated_module(
        tmp_path, "ping_protocol_mock_server", monkeypatch
    ).MockServer

    client_to_server = queue.Queue()
    server_to_client = queue.Queue()
    server = mock_server(client_to_server, server_to_client)
    server.start()

    try:
        client = mock_client(client_to_server, server_to_client)

        ping = ping_protocol(type_id=0, sequence_number=42, payload_size=8)
        response = client.send_and_receive(ping, timeout=2.0)

        assert response is not None
        assert response.type_id == 0
        assert response.sequence_number == 42
        assert response.payload_size == 8
    finally:
        server.stop(timeout=2.0)


def test_mock_server_handles_exceptions(ping_spec, tmp_path, monkeypatch):
    """Test that server does not crash when handler raises an exception."""
    PythonGenerator().generate(ping_spec, tmp_path)

    generate_mock_files(ping_spec, tmp_path, MockClientGenerator)
    generate_mock_files(ping_spec, tmp_path, MockServerGenerator)

    ping_protocol = _import_generated_module(
        tmp_path, "ping_protocol_parser", monkeypatch
    ).PingProtocol
    mock_client = _import_generated_module(
        tmp_path, "ping_protocol_mock_client", monkeypatch
    ).MockClient
    mock_server = _import_generated_module(
        tmp_path, "ping_protocol_mock_server", monkeypatch
    ).MockServer

    handled = threading.Event()

    def error_handler(msg):
        handled.set()
        raise ValueError("Test exception")

    def wait_for_last_error(timeout: float) -> Exception | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if server.last_error is not None:
                return server.last_error
            time.sleep(0.01)
        return server.last_error

    client_to_server = queue.Queue()
    server_to_client = queue.Queue()
    server = mock_server(client_to_server, server_to_client, handler=error_handler)
    server.start()

    try:
        client = mock_client(client_to_server, server_to_client)

        ping = ping_protocol(type_id=0, sequence_number=99, payload_size=8)
        client.send(ping)

        assert handled.wait(timeout=2.0)
        last_error = wait_for_last_error(timeout=2.0)
        assert server.is_alive()
        assert isinstance(last_error, ValueError)
    finally:
        server.stop(timeout=2.0)
