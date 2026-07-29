from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_server.sites_service.cloud import FastFoldSitesClient, PublishedSite


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


def test_publish_waits_until_public_url_is_reachable(
    tmp_path: Path, monkeypatch
) -> None:
    artifact = tmp_path / "site.zip"
    artifact.write_bytes(b"PK\x03\x04")
    url = "https://example-f9a9.sandwalk.site"
    responses = [
        {"id": "site-1", "url": url},
        {
            "deployment": {"id": "dep-1"},
            "upload": {"url": "https://upload.example/form", "fields": {"key": "k"}},
        },
        {},
        {"status": "succeeded", "publicUrl": url},
    ]
    clock = {"now": 0.0}
    ready_checks = {"count": 0}

    client = FastFoldSitesClient(
        api_key="test-key",
        endpoint="https://api.example/v1",
        request_timeout=5,
        wait_timeout=30,
        ready_timeout=10,
    )

    def fake_json(method, path, payload=None):
        del method, path, payload
        return responses.pop(0)

    def fake_ready(candidate: str) -> bool:
        assert candidate == url
        ready_checks["count"] += 1
        return ready_checks["count"] >= 3

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(client, "_json", fake_json)
    monkeypatch.setattr(client, "_upload", MagicMock())
    monkeypatch.setattr(client, "_public_url_ready", fake_ready)
    monkeypatch.setattr(
        "agent_server.sites_service.cloud.time.monotonic",
        lambda: clock["now"],
    )
    monkeypatch.setattr("agent_server.sites_service.cloud.time.sleep", fake_sleep)

    published = client.publish(
        artifact=artifact,
        name="Example",
        local_site_id="local-1",
        content_sha256="abc",
        expanded_size_bytes=12,
        file_count=1,
    )

    assert published == PublishedSite(url=url, site_id="site-1")
    assert ready_checks["count"] == 3


def test_publish_times_out_when_public_url_stays_unreachable(
    tmp_path: Path, monkeypatch
) -> None:
    artifact = tmp_path / "site.zip"
    artifact.write_bytes(b"PK\x03\x04")
    url = "https://example-f9a9.sandwalk.site"
    responses = [
        {"id": "site-1", "url": url},
        {
            "deployment": {"id": "dep-1"},
            "upload": {"url": "https://upload.example/form", "fields": {"key": "k"}},
        },
        {},
        {"status": "succeeded", "publicUrl": url},
    ]
    clock = {"now": 0.0}

    client = FastFoldSitesClient(
        api_key="test-key",
        endpoint="https://api.example/v1",
        wait_timeout=30,
        ready_timeout=3,
    )

    def fake_sleep(seconds):
        clock["now"] += float(seconds)

    monkeypatch.setattr(client, "_json", lambda *a, **k: responses.pop(0))
    monkeypatch.setattr(client, "_upload", MagicMock())
    monkeypatch.setattr(client, "_public_url_ready", lambda _url: False)
    monkeypatch.setattr(
        "agent_server.sites_service.cloud.time.monotonic",
        lambda: clock["now"],
    )
    monkeypatch.setattr("agent_server.sites_service.cloud.time.sleep", fake_sleep)

    with pytest.raises(TimeoutError, match="not reachable"):
        client.publish(
            artifact=artifact,
            name="Example",
            local_site_id="local-1",
            content_sha256="abc",
            expanded_size_bytes=12,
            file_count=1,
        )


def test_request_timeout_is_separate_from_wait_budget() -> None:
    client = FastFoldSitesClient(
        api_key="k",
        timeout=90,
        request_timeout=15,
        ready_timeout=120,
    )
    assert client.request_timeout == 15
    assert client.wait_timeout == 90
    assert client.ready_timeout == 120
