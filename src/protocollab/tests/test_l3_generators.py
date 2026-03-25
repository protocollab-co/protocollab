import importlib
import inspect
import socket
import sys
import time
from pathlib import Path
from typing import Generator

import pytest

from protocollab.generators.l3_client import L3ClientGenerator
from protocollab.generators.l3_server import L3ServerGenerator
from protocollab.generators.python_generator import PythonGenerator
from protocollab.loader import load_protocol

GENERATED_MODULE_NAMES = (
    "ping_protocol_parser",
    "ping_protocol_l3_client",
    "ping_protocol_l3_server",
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
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    file_path = project_root / "examples" / "simple" / "ping_protocol.yaml"
    if not file_path.exists():
        pytest.skip(f"Spec file not found: {file_path}")
    return load_protocol(str(file_path))


def generate_l3_files(spec, output_dir, generator_class):
    generator = generator_class()
    return generator.generate(spec, output_dir)


def test_l3_client_generation(ping_spec, tmp_path, monkeypatch):
    PythonGenerator().generate(ping_spec, tmp_path)

    output_files = generate_l3_files(ping_spec, tmp_path, L3ClientGenerator)
    assert len(output_files) == 1
    assert output_files[0].name == "ping_protocol_l3_client.py"

    module = _import_generated_module(tmp_path, "ping_protocol_l3_client", monkeypatch)
    assert hasattr(module, "L3SocketClient")


def test_l3_server_generation(ping_spec, tmp_path, monkeypatch):
    PythonGenerator().generate(ping_spec, tmp_path)

    output_files = generate_l3_files(ping_spec, tmp_path, L3ServerGenerator)
    assert len(output_files) == 1
    assert output_files[0].name == "ping_protocol_l3_server.py"

    module = _import_generated_module(tmp_path, "ping_protocol_l3_server", monkeypatch)
    assert hasattr(module, "L3SocketServer")
    assert ".listen()" in inspect.getsource(module.L3SocketServer.start)


def test_l3_server_stop_before_start(ping_spec, tmp_path, monkeypatch):
    PythonGenerator().generate(ping_spec, tmp_path)
    generate_l3_files(ping_spec, tmp_path, L3ServerGenerator)

    l3_server = _import_generated_module(
        tmp_path, "ping_protocol_l3_server", monkeypatch
    ).L3SocketServer
    server = l3_server("127.0.0.1", 0)

    server.stop(timeout=0.1)

    assert not server.is_alive()


def test_l3_server_run_requires_initialized_socket(ping_spec, tmp_path, monkeypatch):
    PythonGenerator().generate(ping_spec, tmp_path)
    generate_l3_files(ping_spec, tmp_path, L3ServerGenerator)

    l3_server = _import_generated_module(
        tmp_path, "ping_protocol_l3_server", monkeypatch
    ).L3SocketServer
    server = l3_server("127.0.0.1", 0)

    with pytest.raises(RuntimeError, match=r"called before start\(\)"):
        server._run()


def test_l3_client_server_round_trip(ping_spec, tmp_path, monkeypatch):
    PythonGenerator().generate(ping_spec, tmp_path)
    generate_l3_files(ping_spec, tmp_path, L3ClientGenerator)
    generate_l3_files(ping_spec, tmp_path, L3ServerGenerator)

    ping_protocol = _import_generated_module(
        tmp_path, "ping_protocol_parser", monkeypatch
    ).PingProtocol
    l3_client = _import_generated_module(
        tmp_path, "ping_protocol_l3_client", monkeypatch
    ).L3SocketClient
    l3_server = _import_generated_module(
        tmp_path, "ping_protocol_l3_server", monkeypatch
    ).L3SocketServer

    def ping_handler(request):
        return ping_protocol(
            type_id=1,
            sequence_number=request.sequence_number,
            payload_size=request.payload_size,
        )

    server = l3_server("127.0.0.1", 0, handler=ping_handler, timeout=2.0)
    server.start()

    try:
        host, port = server.address
        client = l3_client(host, port, timeout=2.0)
        ping = ping_protocol(type_id=0, sequence_number=77, payload_size=8)
        response = client.send_and_receive(ping)

        assert response.type_id == 1
        assert response.sequence_number == 77
        assert response.payload_size == 8
        assert server.last_error is None
    finally:
        server.stop(timeout=2.0)


def test_l3_client_send_drains_response(ping_spec, tmp_path, monkeypatch):
    PythonGenerator().generate(ping_spec, tmp_path)
    generate_l3_files(ping_spec, tmp_path, L3ClientGenerator)
    generate_l3_files(ping_spec, tmp_path, L3ServerGenerator)

    ping_protocol = _import_generated_module(
        tmp_path, "ping_protocol_parser", monkeypatch
    ).PingProtocol
    l3_client = _import_generated_module(
        tmp_path, "ping_protocol_l3_client", monkeypatch
    ).L3SocketClient
    l3_server = _import_generated_module(
        tmp_path, "ping_protocol_l3_server", monkeypatch
    ).L3SocketServer

    def ping_handler(request):
        return ping_protocol(
            type_id=1,
            sequence_number=request.sequence_number,
            payload_size=request.payload_size,
        )

    server = l3_server("127.0.0.1", 0, handler=ping_handler, timeout=2.0)
    server.start()

    try:
        client = l3_client(*server.address, timeout=2.0)
        ping = ping_protocol(type_id=0, sequence_number=11, payload_size=8)

        client.send(ping)

        assert server.last_error is None
    finally:
        server.stop(timeout=2.0)


def test_l3_client_receive_is_not_supported(ping_spec, tmp_path, monkeypatch):
    PythonGenerator().generate(ping_spec, tmp_path)
    generate_l3_files(ping_spec, tmp_path, L3ClientGenerator)

    l3_client = _import_generated_module(
        tmp_path, "ping_protocol_l3_client", monkeypatch
    ).L3SocketClient
    client = l3_client("127.0.0.1", 0, timeout=0.5)

    with pytest.raises(NotImplementedError, match="send_and_receive"):
        client.receive()


def test_l3_server_records_handler_exception(ping_spec, tmp_path, monkeypatch):
    PythonGenerator().generate(ping_spec, tmp_path)
    generate_l3_files(ping_spec, tmp_path, L3ClientGenerator)
    generate_l3_files(ping_spec, tmp_path, L3ServerGenerator)

    ping_protocol = _import_generated_module(
        tmp_path, "ping_protocol_parser", monkeypatch
    ).PingProtocol
    l3_client = _import_generated_module(
        tmp_path, "ping_protocol_l3_client", monkeypatch
    ).L3SocketClient
    l3_server = _import_generated_module(
        tmp_path, "ping_protocol_l3_server", monkeypatch
    ).L3SocketServer

    def error_handler(_msg):
        raise ValueError("test handler error")

    server = l3_server("127.0.0.1", 0, handler=error_handler, timeout=0.5)
    server.start()

    try:
        client = l3_client(*server.address, timeout=0.5)
        ping = ping_protocol(type_id=0, sequence_number=1, payload_size=8)

        with pytest.raises((ConnectionError, TimeoutError, socket.timeout, OSError)):
            client.send_and_receive(ping)

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and server.last_error is None:
            time.sleep(0.01)

        assert isinstance(server.last_error, ValueError)
    finally:
        server.stop(timeout=2.0)


def test_l3_server_preserves_accept_oserror_context(ping_spec, tmp_path, monkeypatch):
    PythonGenerator().generate(ping_spec, tmp_path)
    generate_l3_files(ping_spec, tmp_path, L3ServerGenerator)

    l3_server = _import_generated_module(
        tmp_path, "ping_protocol_l3_server", monkeypatch
    ).L3SocketServer
    server = l3_server("127.0.0.1", 0, timeout=0.5)

    original_error = OSError("accept failed")

    class FailingSocket:
        def accept(self):
            raise original_error

    server._server_socket = FailingSocket()
    server._run()

    assert server.last_error is original_error
