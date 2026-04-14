"""CLI tests for generate commands."""

from protocollab.main import cli


class TestCLIGenerate:
    def test_generate_python_exits_zero(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "python", str(ping_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 0

    def test_generate_python_prints_path(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "python", str(ping_yaml), "-o", str(tmp_path)])
        assert "Generated:" in result.output

    def test_generate_wireshark_exits_zero(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "wireshark", str(ping_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 0

    def test_generate_mock_client_also_generates_parser(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "mock-client", str(ping_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "ping_protocol_parser.py").exists()
        assert (tmp_path / "ping_protocol_mock_client.py").exists()
        assert result.output.count("Generated:") == 2

    def test_generate_mock_server_also_generates_parser(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "mock-server", str(ping_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "ping_protocol_parser.py").exists()
        assert (tmp_path / "ping_protocol_mock_server.py").exists()
        assert result.output.count("Generated:") == 2

    def test_generate_l3_client_also_generates_parser(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "l3-client", str(ping_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "ping_protocol_parser.py").exists()
        assert (tmp_path / "ping_protocol_l3_client.py").exists()
        assert result.output.count("Generated:") == 2

    def test_generate_l2_client_also_generates_parser(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "l2-client", str(ping_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "ping_protocol_parser.py").exists()
        assert (tmp_path / "ping_protocol_l2_client.py").exists()
        assert result.output.count("Generated:") == 2

    def test_generate_l2_server_also_generates_parser(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "l2-server", str(ping_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "ping_protocol_parser.py").exists()
        assert (tmp_path / "ping_protocol_l2_server.py").exists()
        assert result.output.count("Generated:") == 2

    def test_generate_l3_server_also_generates_parser(self, runner, ping_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "l3-server", str(ping_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "ping_protocol_parser.py").exists()
        assert (tmp_path / "ping_protocol_l3_server.py").exists()
        assert result.output.count("Generated:") == 2

    def test_generate_missing_file_exits_one(self, runner, tmp_path):
        result = runner.invoke(cli, ["generate", "python", "/no/such/file.yaml", "-o", str(tmp_path)])
        assert result.exit_code == 1

    def test_generate_invalid_yaml_exits_two(self, runner, invalid_yaml, tmp_path):
        result = runner.invoke(cli, ["generate", "python", str(invalid_yaml), "-o", str(tmp_path)])
        assert result.exit_code == 2

    def test_generate_bad_type_exits_four(self, runner, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("meta:\n  id: p\n  endian: le\nseq:\n  - id: x\n    type: unknown_type\n")
        out = tmp_path / "out"
        result = runner.invoke(cli, ["generate", "python", str(bad), "-o", str(out)])
        assert result.exit_code == 4

    def test_generate_help(self, runner):
        result = runner.invoke(cli, ["generate", "--help"])
        assert result.exit_code == 0
        assert "python" in result.output
        assert "wireshark" in result.output
        assert "l2-client" in result.output
        assert "l2-server" in result.output
        assert "l3-client" in result.output
        assert "l3-server" in result.output
        assert "mock-client" in result.output
        assert "mock-server" in result.output

    def test_generate_creates_output_dir(self, runner, ping_yaml, tmp_path):
        out = tmp_path / "new_dir"
        runner.invoke(cli, ["generate", "python", str(ping_yaml), "-o", str(out)])
        assert out.exists()
