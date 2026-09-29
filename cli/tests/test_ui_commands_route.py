"""POST /v1/ui/commands publishes UI commands to the session event bus."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from agent_server.routes.ui_commands import UiCommandRequest, build_ui_command_payload


def test_open_split_payload_with_layout() -> None:
    payload = build_ui_command_payload(
        UiCommandRequest(action="open_split", session_ids=["a", " b ", ""], layout={"rows": 4, "cols": 4})
    )
    assert payload == {"action": "open_split", "sessionIds": ["a", "b"], "layout": {"rows": 4, "cols": 4}}


def test_open_split_without_layout_omits_key() -> None:
    payload = build_ui_command_payload(UiCommandRequest(action="open_split", session_ids=["a", "b"]))
    assert "layout" not in payload


def test_camel_case_input_is_accepted() -> None:
    request = UiCommandRequest.model_validate({"action": "open_split", "sessionIds": ["a", "b"]})
    assert build_ui_command_payload(request)["sessionIds"] == ["a", "b"]


@pytest.mark.parametrize(
    "request_kwargs, detail",
    [
        ({"action": "reboot"}, "Unsupported UI action"),
        ({"action": "open_split", "session_ids": ["only-one"]}, "at least two"),
        ({"action": "open_split", "session_ids": ["a", "b"], "layout": {"rows": 0, "cols": 2}}, "rows >= 1"),
    ],
)
def test_rejects_bad_requests(request_kwargs: dict, detail: str) -> None:
    with pytest.raises(HTTPException) as exc:
        build_ui_command_payload(UiCommandRequest(**request_kwargs))
    assert exc.value.status_code == 400
    assert detail in exc.value.detail


def test_route_publishes_to_bus(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from agent_server.routes import ui_commands

    published: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        ui_commands.session_event_bus, "publish", lambda kind, payload: published.append((kind, payload))
    )
    app = FastAPI()
    ui_commands.register_ui_command_routes(app, deps=None)  # type: ignore[arg-type]
    client = TestClient(app)

    response = client.post(
        "/v1/ui/commands",
        json={"action": "open_split", "sessionIds": ["s1", "s2", "s3", "s4"], "layout": {"rows": 2, "cols": 2}},
    )
    assert response.status_code == 202
    assert response.json() == {"accepted": True, "action": "open_split"}
    assert published == [
        ("ui.command", {"action": "open_split", "sessionIds": ["s1", "s2", "s3", "s4"], "layout": {"rows": 2, "cols": 2}})
    ]

    assert client.post("/v1/ui/commands", json={"action": "nope"}).status_code == 400
