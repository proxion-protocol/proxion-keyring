import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, mock_open
from proxion_keyring.cli import cli

def test_suite_ls():
    runner = CliRunner()
    with patch("os.listdir", return_value=["adguard-integration", "mastodon-integration"]), \
         patch("os.path.isdir", return_value=True):
        result = runner.invoke(cli, ["suite", "ls"])
        assert result.exit_code == 0
        assert "adguard-integration" in result.output
        assert "mastodon-integration" in result.output

def test_dns_enable_command():
    runner = CliRunner()
    # Mock the adapter methods
    with patch("proxion_keyring.cli.adapter.get_active_interface_index", return_value=16), \
         patch("proxion_keyring.cli.adapter.set_dns", return_value=None):
        
        result = runner.invoke(cli, ["mesh", "dns-enable"])
        assert result.exit_code == 0
        assert "Requesting host DNS change" in result.output

def test_install_command_path_resolution():
    runner = CliRunner()
    # Mock path resolution and docker-compose
    with patch("proxion_keyring.cli.registry.get_app_path", return_value="/fake/app"), \
         patch("proxion_keyring.cli.registry.get_subpath", return_value="net/adguard"), \
         patch("proxion_keyring.cli.os.path.exists", return_value=True), \
         patch("proxion_keyring.cli._run_docker_compose") as mock_dc, \
         patch("proxion_keyring.cli._provision_app", MagicMock()), \
         patch("proxion_keyring.cli.open", mock_open()):
        
        mock_dc.return_value.returncode = 0
        
        result = runner.invoke(cli, ["suite", "install", "adguard"])
        assert result.exit_code == 0
        assert "installing" in result.output.lower() or "deploying" in result.output.lower()
