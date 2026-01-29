import os
import sys
import unittest
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.abspath(os.path.join(ROOT, "..", "proxion-core", "src")))

from cp.control_plane import ControlPlane, PolicyDecision
from cp.pod_storage import ensure_pod_containers, write_receipt
from rs.service import ResourceServer
from proxion_core import RequestContext


class FakePodClient:
    def __init__(self) -> None:
        self.containers = []
        self.objects = {}

    def create_container(self, url: str) -> None:
        self.containers.append(url)

    def write_json(self, url: str, payload: dict) -> None:
        self.objects[url] = payload


class StaticPolicy:
    def __init__(self) -> None:
        self.decision = PolicyDecision(
            permissions={("channel.bootstrap", "rs:wg0")},
            ttl_seconds=60,
            caveats=[],
        )

    def decide(self, rp_pubkey: str) -> PolicyDecision:
        _ = rp_pubkey
        return self.decision


class KleitikonTests(unittest.TestCase):
    def test_pod_container_creation(self) -> None:
        pod = FakePodClient()
        base = "https://pod.example/"
        paths = ensure_pod_containers(pod, base)
        self.assertEqual(set(paths), set(pod.containers))
        self.assertIn("https://pod.example/kleitikon/", pod.containers)

    def test_receipt_write(self) -> None:
        pod = FakePodClient()
        base = "https://pod.example/"
        receipt = {"receipt_id": "rcpt-1", "type": "KleitikonReceipt"}
        url = write_receipt(pod, base, receipt)
        self.assertIn(url, pod.objects)
        self.assertEqual(pod.objects[url]["receipt_id"], "rcpt-1")

    def test_pt_mint_redeem_integration_mock_rs(self) -> None:
        signing_key = b"test-key"
        pod = FakePodClient()
        policy = StaticPolicy()
        cp = ControlPlane(signing_key, policy, pod, "https://pod.example/")
        rs = ResourceServer(signing_key)

        ticket_id = cp.mint_pt(30)
        now = datetime.now(timezone.utc)
        token = cp.redeem_pt(
            ticket_id,
            rp_pubkey="rp-key",
            aud="rs-1",
            holder_key_fingerprint="fp1",
            now=now,
        )
        ctx = RequestContext(
            action="channel.bootstrap",
            resource="rs:wg0",
            aud="rs-1",
            now=now,
        )
        decision = rs.authorize(token, ctx, {"holder_key_fingerprint": "fp1"})
        self.assertTrue(decision.allowed)


if __name__ == "__main__":
    unittest.main()
