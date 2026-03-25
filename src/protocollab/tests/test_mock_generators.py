"""Tests for protocollab.generators.mock_client."""

import sys
import queue
import time
import importlib
from pathlib import Path

import pytest

from protocollab.generators.mock_client import MockClientGenerator
from protocollab.generators.mock_server import MockServerGenerator
from protocollab.generators.python_generator import PythonGenerator
from protocollab.loader import load_protocol


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


def test_mock_client_generation(ping_spec, tmp_path):
    """Test that mock client generator creates a file and its content is importable."""
    PythonGenerator().generate(ping_spec, tmp_path)

    output_files = generate_mock_files(ping_spec, tmp_path, MockClientGenerator)
    assert len(output_files) == 1
    generated_file = output_files[0]
    assert generated_file.exists()
    assert generated_file.name == "ping_protocol_mock_client.py"

    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module("ping_protocol_mock_client")
        assert hasattr(module, "MockClient")
        mock_client = module.MockClient
        assert callable(getattr(mock_client, "send", None))
        assert callable(getattr(mock_client, "receive", None))
        assert callable(getattr(mock_client, "send_and_receive", None))
    finally:
        sys.path.pop(0)


def test_mock_server_generation(ping_spec, tmp_path):
    """Test that mock server generator creates a file and its content is importable."""
    PythonGenerator().generate(ping_spec, tmp_path)

    output_files = generate_mock_files(ping_spec, tmp_path, MockServerGenerator)
    assert len(output_files) == 1
    generated_file = output_files[0]
    assert generated_file.exists()
    assert generated_file.name == "ping_protocol_mock_server.py"

    sys.path.insert(0, str(tmp_path))
    try:
        module = importlib.import_module("ping_protocol_mock_server")
        assert hasattr(module, "MockServer")
        mock_server = module.MockServer
        assert callable(getattr(mock_server, "start", None))
        assert callable(getattr(mock_server, "stop", None))
    finally:
        sys.path.pop(0)


def test_mock_client_server_interaction(ping_spec, tmp_path):
    """Test full interaction between generated client and server."""
    PythonGenerator().generate(ping_spec, tmp_path)

    generate_mock_files(ping_spec, tmp_path, MockClientGenerator)
    generate_mock_files(ping_spec, tmp_path, MockServerGenerator)

    sys.path.insert(0, str(tmp_path))
    try:
        ping_protocol = importlib.import_module("ping_protocol_parser").PingProtocol
        mock_client = importlib.import_module("ping_protocol_mock_client").MockClient
        mock_server = importlib.import_module("ping_protocol_mock_server").MockServer

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

        client = mock_client(client_to_server, server_to_client)

        ping = ping_protocol(type_id=0, sequence_number=123, payload_size=16)
        response = client.send_and_receive(ping, timeout=2.0)

        assert response is not None
        assert response.type_id == 1
        assert response.sequence_number == 123
        assert response.payload_size == 16

        server.stop()
    finally:
        sys.path.pop(0)


def test_mock_client_timeout(ping_spec, tmp_path):
    """Test that client times out when no response arrives."""
    PythonGenerator().generate(ping_spec, tmp_path)

    generate_mock_files(ping_spec, tmp_path, MockClientGenerator)

    sys.path.insert(0, str(tmp_path))
    try:
        ping_protocol = importlib.import_module("ping_protocol_parser").PingProtocol
        mock_client = importlib.import_module("ping_protocol_mock_client").MockClient

        client_to_server = queue.Queue()
        server_to_client = queue.Queue()
        client = mock_client(client_to_server, server_to_client)

        ping = ping_protocol(type_id=0, sequence_number=1, payload_size=8)
        client.send(ping)
        response = client.receive(timeout=0.5)

        assert response is None
    finally:
        sys.path.pop(0)


def test_mock_server_custom_handler(ping_spec, tmp_path):
    """Test that server uses the provided custom handler."""
    PythonGenerator().generate(ping_spec, tmp_path)

    generate_mock_files(ping_spec, tmp_path, MockClientGenerator)
    generate_mock_files(ping_spec, tmp_path, MockServerGenerator)

    sys.path.insert(0, str(tmp_path))
    try:
        ping_protocol = importlib.import_module("ping_protocol_parser").PingProtocol
        mock_client = importlib.import_module("ping_protocol_mock_client").MockClient
        mock_server = importlib.import_module("ping_protocol_mock_server").MockServer

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

        client = mock_client(client_to_server, server_to_client)

        ping = ping_protocol(type_id=0, sequence_number=100, payload_size=8)
        response = client.send_and_receive(ping, timeout=2.0)

        assert response is not None
        assert response.sequence_number == 101
        assert response.type_id == 0  # unchanged
    finally:
        sys.path.pop(0)


def test_mock_server_default_handler(ping_spec, tmp_path):
    """Test default echo handler."""
    PythonGenerator().generate(ping_spec, tmp_path)

    generate_mock_files(ping_spec, tmp_path, MockClientGenerator)
    generate_mock_files(ping_spec, tmp_path, MockServerGenerator)

    sys.path.insert(0, str(tmp_path))
    try:
        ping_protocol = importlib.import_module("ping_protocol_parser").PingProtocol
        mock_client = importlib.import_module("ping_protocol_mock_client").MockClient
        mock_server = importlib.import_module("ping_protocol_mock_server").MockServer

        client_to_server = queue.Queue()
        server_to_client = queue.Queue()
        server = mock_server(client_to_server, server_to_client)
        server.start()

        client = mock_client(client_to_server, server_to_client)

        ping = ping_protocol(type_id=0, sequence_number=42, payload_size=8)
        response = client.send_and_receive(ping, timeout=2.0)

        assert response is not None
        assert response.type_id == 0
        assert response.sequence_number == 42
        assert response.payload_size == 8
    finally:
        sys.path.pop(0)


def test_mock_server_handles_exceptions(ping_spec, tmp_path):
    """Test that server does not crash when handler raises an exception."""
    PythonGenerator().generate(ping_spec, tmp_path)

    generate_mock_files(ping_spec, tmp_path, MockClientGenerator)
    generate_mock_files(ping_spec, tmp_path, MockServerGenerator)

    sys.path.insert(0, str(tmp_path))
    try:
        ping_protocol = importlib.import_module("ping_protocol_parser").PingProtocol
        mock_client = importlib.import_module("ping_protocol_mock_client").MockClient
        mock_server = importlib.import_module("ping_protocol_mock_server").MockServer

        def error_handler(msg):
            raise ValueError("Test exception")

        client_to_server = queue.Queue()
        server_to_client = queue.Queue()
        server = mock_server(client_to_server, server_to_client, handler=error_handler)
        server.start()

        client = mock_client(client_to_server, server_to_client)

        ping = ping_protocol(type_id=0, sequence_number=99, payload_size=8)
        client.send(ping)

        # Give server time to process
        time.sleep(0.5)

        # Server thread should still be alive
        assert server._thread.is_alive()

        # Send another message to ensure server didn't crash
        client.send(ping)
        time.sleep(0.5)
        # No response expected, just no exception
    finally:
        sys.path.pop(0)
