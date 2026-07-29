from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_server.sites_service.cloud import FastFoldSitesClient


def test_publish_times_out_with_last_status(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "site.zip"
    artifact.write_bytes(b"PK\x03\x04")

    responses = [
        {"id": "site-1", "url": "https://example.sandwalk.site"},
        {
            "deployment": {"id": "dep-1"},
            "upload": {"url": "https://upload.example/form", "fields": {"key": "k"}},
        },
        {},  # finalize
        {"status": "queued"},
        {"status": "processing"},
    ]
    clock = {"now": 0.0}

    client = FastFoldSitesClient(
        api_key="test-key",
        endpoint="https://api.example/v1",
        request_timeout=5,
        wait_timeout=3,
    )

    def fake_json(method, path, payload=None):
        del method, path, payload
        return responses.pop(0)

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    upload = MagicMock()
    monkeypatch.setattr(client, "_json", fake_json)
    monkeypatch.setattr(client, "_upload", upload)
    monkeypatch.setattr(
        "agent_server.sites_service.cloud.time.monotonic",
        lambda: clock["now"],
    )
    monkeypatch.setattr("agent_server.sites_service.cloud.time.sleep", fake_sleep)

    with pytest.raises(TimeoutError, match="last status: processing"):
        client.publish(
            artifact=artifact,
            name="Example",
            local_site_id="local-1",
            content_sha256="abc",
            expanded_size_bytes=12,
            file_count=1,
        )
    upload.assert_called_once()


def test_request_timeout_is_separate_from_wait_budget() -> None:
    client = FastFoldSitesClient(
        api_key="k",
        timeout=90,
        request_timeout=15,
    )
    assert client.request_timeout == 15
    assert client.wait_timeout == 90
