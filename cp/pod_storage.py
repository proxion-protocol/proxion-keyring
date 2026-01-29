"""Solid Pod storage interface for Kleitikon."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class PodClient(Protocol):
    def create_container(self, url: str) -> None:
        ...

    def write_json(self, url: str, payload: dict) -> None:
        ...


def ensure_pod_containers(pod_client: PodClient, base_url: str) -> list[str]:
    root = base_url.rstrip("/") + "/kleitikon/"
    paths = [
        root,
        f"{root}policies/",
        f"{root}receipts/",
        f"{root}audit/",
        f"{root}devices/",
        f"{root}config/",
    ]
    for path in paths:
        pod_client.create_container(path)
    return paths


def write_receipt(pod_client: PodClient, base_url: str, receipt: dict) -> str:
    root = base_url.rstrip("/") + "/kleitikon/receipts/"
    receipt_id = receipt.get("receipt_id", "receipt")
    url = f"{root}{receipt_id}.jsonld"
    pod_client.write_json(url, receipt)
    return url
