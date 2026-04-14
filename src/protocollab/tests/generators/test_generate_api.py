"""Tests for generate() public API behavior."""

import pytest

from protocollab.generators import generate


class TestGenerateAPI:
    def test_generate_python_returns_path(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="python", output_dir=tmp_path)
        assert len(paths) == 1
        assert paths[0].exists()

    def test_generate_wireshark_returns_path(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="wireshark", output_dir=tmp_path)
        assert len(paths) == 1
        assert paths[0].exists()

    def test_generate_str_output_dir(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="python", output_dir=str(tmp_path))
        assert paths[0].exists()

    def test_generate_mock_client_returns_parser_and_mock_paths(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="mock-client", output_dir=tmp_path)
        assert len(paths) == 2
        assert [path.name for path in paths] == [
            "ping_protocol_parser.py",
            "ping_protocol_mock_client.py",
        ]

    def test_generate_mock_server_returns_parser_and_mock_paths(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="mock-server", output_dir=tmp_path)
        assert len(paths) == 2
        assert [path.name for path in paths] == [
            "ping_protocol_parser.py",
            "ping_protocol_mock_server.py",
        ]

    def test_generate_l3_client_returns_parser_and_runtime_paths(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="l3-client", output_dir=tmp_path)
        assert len(paths) == 2
        assert [path.name for path in paths] == [
            "ping_protocol_parser.py",
            "ping_protocol_l3_client.py",
        ]

    def test_generate_l3_server_returns_parser_and_runtime_paths(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="l3-server", output_dir=tmp_path)
        assert len(paths) == 2
        assert [path.name for path in paths] == [
            "ping_protocol_parser.py",
            "ping_protocol_l3_server.py",
        ]

    def test_generate_l2_client_returns_parser_and_runtime_paths(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="l2-client", output_dir=tmp_path)
        assert len(paths) == 2
        assert [path.name for path in paths] == [
            "ping_protocol_parser.py",
            "ping_protocol_l2_client.py",
        ]

    def test_generate_l2_server_returns_parser_and_runtime_paths(self, ping_spec, tmp_path):
        paths = generate(ping_spec, target="l2-server", output_dir=tmp_path)
        assert len(paths) == 2
        assert [path.name for path in paths] == [
            "ping_protocol_parser.py",
            "ping_protocol_l2_server.py",
        ]

    def test_unknown_target_in_generate(self, tmp_path):
        spec = {"meta": {"id": "p"}, "seq": []}
        with pytest.raises(ValueError, match="Unknown target"):
            generate(spec, target="cobol", output_dir=tmp_path)
