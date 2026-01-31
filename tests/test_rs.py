"""Unit tests for Kleitikon Resource Server."""

import pytest
import os

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rs.service import ResourceServer, WireGuardConfig, ConnectionMaterial


class TestResourceServer:
    """Tests for ResourceServer."""

    @pytest.fixture
    def rs(self):
        """Create a ResourceServer instance."""
        signing_key = b"test-signing-key-32-bytes-long!!"
        wg = WireGuardConfig(
            enabled=True,
            interface="wg0",
            endpoint="test.example.com:51820",
            server_pubkey="test-pubkey",
        )
        return ResourceServer(signing_key=signing_key, wg_config=wg)

    def test_wg_peer_add_blocked_by_default(self, rs):
        """wg_peer_add should fail in NO_MUTATION mode."""
        with pytest.raises(RuntimeError, match="mutation disabled"):
            rs.wg_peer_add("pubkey", ["10.0.0.2/32"])

    def test_wg_peer_remove_blocked_by_default(self, rs):
        """wg_peer_remove should fail in NO_MUTATION mode."""
        with pytest.raises(RuntimeError, match="mutation disabled"):
            rs.wg_peer_remove("pubkey")

    def test_connection_material_format(self):
        """ConnectionMaterial should have correct structure."""
        material = ConnectionMaterial(
            dp="wireguard",
            interface="wg0",
            client_address="10.0.0.2/32",
            client_dns=["10.0.0.1"],
            server_endpoint="example.com:51820",
            server_pubkey="pubkey",
            allowed_ips=["10.0.0.0/24"],
            expires_at=1234567890,
            wg_config_template="[Interface]\n...",
        )
        d = material.to_dict()

        assert d["type"] == "KleitikonConnectionMaterial"
        assert d["dp"] == "wireguard"
        assert d["interface"] == "wg0"
        assert d["client"]["address"] == "10.0.0.2/32"
        assert d["server"]["endpoint"] == "example.com:51820"
        assert "10.0.0.0/24" in d["allowed_ips"]


class TestWireGuardConfig:
    """Tests for WireGuardConfig."""

    def test_default_mutation_disabled(self):
        """Default config should have mutation disabled."""
        wg = WireGuardConfig()
        assert wg.enabled is False

    def test_custom_config(self):
        """WireGuardConfig should accept custom values."""
        wg = WireGuardConfig(
            enabled=True,
            interface="wg1",
            endpoint="custom.example:51820",
        )
        assert wg.enabled is True
        assert wg.interface == "wg1"
