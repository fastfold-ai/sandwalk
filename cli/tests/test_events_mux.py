from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent_server.app import create_app
from agent_server.routes.events_mux import parse_after_cursors, parse_session_ids


def test_parse_session_ids_dedupes_and_caps() -> None:
    ids = parse_session_ids(" a, a, b, ,c ")
    assert ids == ["a", "b", "c"]
    many = parse_session_ids(",".join(str(i) for i in range(20)))
    assert len(many) == 16


def test_parse_after_cursors() -> None:
    assert parse_after_cursors("s1:12,s2:0,bad,s3:x") == {"s1": 12, "s2": 0}


def test_health_advertises_event_mux(tmp_path: Path) -> None:
    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        body = client.get("/v1/health").json()
        assert body["capabilities"]["eventMux"] is True
