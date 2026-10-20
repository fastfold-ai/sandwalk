"""Coverage for usage parsing and UniProt function prediction."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from agent_server.usage_service.parse import (
    active_model_id,
    active_provider,
    canonicalize_usage_model,
    day_key_from_epoch,
    day_key_from_timestamp,
    infer_provider,
    parse_usage_tokens,
    resolve_client_surface,
    surface_for_session,
    token_int,
)
from tools.protein_function import function_predict


def test_usage_parse_edges(monkeypatch) -> None:
    assert token_int(None, "input_tokens") == 0
    assert token_int({"input_tokens": None, "inputTokens": "nope", "n": -3}, "input_tokens", "inputTokens", "n") == 0
    parsed = parse_usage_tokens({"inputTokens": 4, "cacheReadTokens": 2, "cacheCreationTokens": 1})
    assert parsed["input_tokens"] == 4
    assert parsed["cache_read_tokens"] == 2

    assert day_key_from_timestamp(datetime(2026, 10, 19, tzinfo=UTC)) == "2026-10-19"
    assert day_key_from_timestamp("2026-10-19T00:00:00Z") == "2026-10-19"
    assert day_key_from_timestamp("2026-10-19 not iso") == "2026-10-19"
    assert len(day_key_from_timestamp("nope")) == 10
    assert len(day_key_from_timestamp("")) == 10
    assert day_key_from_epoch("bad")
    assert day_key_from_epoch(-1)
    assert day_key_from_epoch(1_700_000_000)

    def boom():
        raise RuntimeError("settings")

    monkeypatch.setattr("agent_server.settings_service.SettingsService.get", boom)
    assert active_model_id() is None
    assert active_provider() is None

    monkeypatch.setattr("agent.model_catalog.catalog_provider_for_model", boom)
    assert infer_provider("gpt-4o", "unknown") == "unknown"
    assert infer_provider("gpt-4o", "openai") == "openai"

    assert canonicalize_usage_model(None) == ("unknown", "unknown")
    assert canonicalize_usage_model("luna-pro")[1]
    provider, model = canonicalize_usage_model("moonshotai/kimi", provider="")
    assert provider in {"moonshot", "unknown", "moonshotai"}
    assert canonicalize_usage_model("custom-model", provider="anthropic")[0] in {"anthropic", "unknown"}

    assert surface_for_session(None) == "unknown"
    assert surface_for_session(SimpleNamespace(client_surface="ui")) == "ui"
    assert surface_for_session(SimpleNamespace(client_surface=None, source="slack")) == "slack"
    assert surface_for_session(SimpleNamespace(client_surface=None, source="bench")) == "unknown"
    assert resolve_client_surface(source="slack") == "slack"
    assert resolve_client_surface(body="ui", header="cli") == "ui"
    assert resolve_client_surface(body="nope") is None


def test_function_predict_errors_and_annotations(monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        return None, "down"

    monkeypatch.setattr("tools.protein_function.request", fail)
    assert "UniProt API error" in function_predict("P38398")["error"]
    assert "UniProt API error" in function_predict("BRCA1")["error"]

    def status(code, payload):
        def _request(*_args, **_kwargs):
            return SimpleNamespace(status_code=code, json=lambda: payload), None

        return _request

    monkeypatch.setattr("tools.protein_function.request", status(404, {}))
    assert "HTTP 404" in function_predict("P38398")["error"]
    assert "HTTP 404" in function_predict("BRCA1")["error"]

    def bad_json(*_args, **_kwargs):
        def _json():
            raise ValueError("nope")

        return SimpleNamespace(status_code=200, json=_json), None

    monkeypatch.setattr("tools.protein_function.request", bad_json)
    assert "Invalid UniProt" in function_predict("P38398")["error"]
    assert "Invalid UniProt" in function_predict("BRCA1")["error"]

    monkeypatch.setattr("tools.protein_function.request", status(200, {"results": []}))
    assert "no uniprot entry" in function_predict("BRCA1")["error"].lower()

    entry = {
        "primaryAccession": "P38398",
        "proteinDescription": {"recommendedName": {"fullName": {"value": "BRCA1"}}},
        "comments": [
            {"commentType": "FUNCTION", "texts": [{"value": "repairs DNA"}]},
            {"commentType": "SUBCELLULAR LOCATION", "subcellularLocations": [{"location": {"value": "Nucleus"}}]},
            {"commentType": "TISSUE SPECIFICITY", "texts": [{"value": "breast"}]},
            {"commentType": "DISEASE", "disease": {"diseaseId": "breast cancer", "description": "risk", "acronym": "BC"}},
            {"commentType": "CATALYTIC ACTIVITY", "reaction": {"name": "none"}},
        ],
        "features": [
            {"type": "Domain", "description": "BRCT", "location": {"start": {"value": 1}, "end": {"value": 10}}},
            {"type": "Modified residue", "description": "phospho", "location": {"start": {"value": 2}}},
            {"type": "Active site", "description": "site", "location": {"start": {"value": 3}}},
            {"type": "Binding site", "description": "bind", "location": {"start": {"value": 4}, "end": {"value": 5}}},
        ],
        "uniProtKBCrossReferences": [
            {"database": "GO", "id": "GO:1", "properties": [{"key": "GoTerm", "value": "P:repair"}]},
            {"database": "GO", "id": "GO:2", "properties": [{"key": "GoTerm", "value": "F:binding"}]},
            {"database": "GO", "id": "GO:3", "properties": [{"key": "GoTerm", "value": "C:nucleus"}]},
        ],
        "keywords": [{"name": "DNA repair"}],
    }
    monkeypatch.setattr("tools.protein_function.request", status(200, entry))
    result = function_predict("P38398")
    assert result.get("error") is None or "BRCA1" in str(result)
    assert "Nucleus" in str(result) or "repair" in str(result).lower()
