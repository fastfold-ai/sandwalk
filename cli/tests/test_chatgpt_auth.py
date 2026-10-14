"""Sign in with ChatGPT: credential store, PKCE flow, refresh, and the API routes.

Nothing here touches ``auth.openai.com``. Token-endpoint and JWKS calls are
stubbed so the tests exercise our handling of OpenAI's documented shapes.
"""

from __future__ import annotations

import os
import stat
import time
import urllib.parse
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent.config import chatgpt_auth as ca


@pytest.fixture(autouse=True)
def _isolated_files(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ca, "CREDENTIALS_FILE", tmp_path / "chatgpt-auth.json")
    monkeypatch.setattr(ca, "HOST_ID_FILE", tmp_path / "chatgpt-host-id")
    # Each test starts with no pending attempts.
    ca._pending.clear()
    yield
    ca._pending.clear()


def _creds(**overrides) -> ca.ChatGPTCredentials:
    base = {
        "email": "user@example.com",
        "subject": "sub-1",
        "client_id": "oaiapp_abc",
        "ext_agent_host_id": "urn:uuid:11111111-1111-4111-8111-111111111111",
        "id_token": "id.tok.en",
        "access_token": "access-1",
        "refresh_token": "refresh-1",
        "scopes": ca.SCOPES.split(),
        "expires_at": time.time() + 3600,
    }
    base.update(overrides)
    return ca.ChatGPTCredentials(**base)


# --- host id + file --------------------------------------------------------


def test_host_id_is_stable_urn_uuid_and_private():
    first = ca.host_id()
    second = ca.host_id()
    assert first == second
    assert first.startswith("urn:uuid:")
    mode = stat.S_IMODE(os.stat(ca.HOST_ID_FILE).st_mode)
    assert mode == 0o600


def test_save_and_load_credentials_round_trip_with_0600():
    creds = _creds()
    ca.save_credentials(creds)
    assert stat.S_IMODE(os.stat(ca.CREDENTIALS_FILE).st_mode) == 0o600
    loaded = ca.load_credentials()
    assert loaded is not None
    assert loaded.email == "user@example.com"
    assert loaded.client_id == "oaiapp_abc"
    assert loaded.plan_usage_granted is True
    assert ca.is_connected() is True


def test_missing_plan_scope_is_not_connected():
    ca.save_credentials(_creds(scopes=["openid", "profile", "email"]))
    assert ca.is_connected() is False
    assert ca.status()["connected"] is False
    assert ca.status()["plan_usage"] is False


def test_status_never_leaks_tokens():
    ca.save_credentials(_creds())
    summary = ca.status()
    assert "access_token" not in summary
    assert "refresh_token" not in summary
    assert "id_token" not in summary
    assert summary == {
        "connected": True,
        "email": "user@example.com",
        "plan_usage": True,
        "expires_at": pytest.approx(ca.load_credentials().expires_at),
    }


# --- begin_login -----------------------------------------------------------


def test_begin_login_first_time_uses_dynamic_registration():
    started = ca.begin_login(redirect_uri="http://127.0.0.1:4321/auth/callback")
    parsed = urllib.parse.urlparse(started["url"])
    assert parsed.scheme == "https" and parsed.netloc == "auth.openai.com"
    q = urllib.parse.parse_qs(parsed.query)
    assert q["client_id"] == [ca.DYNAMIC_CLIENT_ID]
    assert q["agent_name_hint"] == [ca.AGENT_NAME]
    assert q["redirect_uri"] == ["http://127.0.0.1:4321/auth/callback"]
    assert q["resource"] == [ca.RESOURCE]
    assert q["code_challenge_method"] == ["S256"]
    assert q["response_type"] == ["code"]
    assert set(q["scope"][0].split()) == set(ca.SCOPES.split())
    assert q["ext_agent_host_id"][0].startswith("urn:uuid:")
    assert q["state"] == [started["state"]]
    assert "id_token_hint" not in q
    assert started["state"] in ca._pending


def test_begin_login_reauth_reuses_issued_client_and_hints():
    ca.save_credentials(_creds())
    started = ca.begin_login(redirect_uri="http://127.0.0.1:4321/auth/callback")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(started["url"]).query)
    assert q["client_id"] == ["oaiapp_abc"]
    assert q["id_token_hint"] == ["id.tok.en"]
    assert q["login_hint"] == ["user@example.com"]
    assert "agent_name_hint" not in q


@pytest.mark.parametrize(
    "bad",
    [
        "https://127.0.0.1:1/auth/callback",  # must be http
        "http://localhost:1/auth/callback",  # must be 127.0.0.1 literally
        "http://127.0.0.1:1/callback",  # path must match exactly
    ],
)
def test_begin_login_rejects_bad_redirect(bad):
    with pytest.raises(ca.ChatGPTAuthError):
        ca.begin_login(redirect_uri=bad)


# --- complete_login --------------------------------------------------------


def _stub_token(monkeypatch, payload):
    calls = []

    def fake_post(form):
        calls.append(form)
        return dict(payload)

    monkeypatch.setattr(ca, "_post_token", fake_post)
    return calls


def _stub_id_token(monkeypatch, *, sub="sub-1", email="user@example.com"):
    def fake_validate(id_token, *, client_id, nonce):
        return {"sub": sub, "email": email, "aud": client_id, "nonce": nonce}

    monkeypatch.setattr(ca, "_validate_id_token", fake_validate)


def test_complete_login_first_time_persists_issued_client(monkeypatch):
    started = ca.begin_login(redirect_uri="http://127.0.0.1:4321/auth/callback")
    calls = _stub_token(
        monkeypatch,
        {
            "access_token": "at-1",
            "refresh_token": "rt-1",
            "id_token": "idt",
            "expires_in": 3600,
            "scope": ca.SCOPES,
        },
    )
    _stub_id_token(monkeypatch)

    creds = ca.complete_login(code="code-1", state=started["state"], callback_client_id="oaiapp_new")

    assert creds.client_id == "oaiapp_new"
    assert creds.access_token == "at-1"
    assert creds.refresh_token == "rt-1"
    assert creds.email == "user@example.com"
    assert calls[0]["grant_type"] == "authorization_code"
    assert calls[0]["client_id"] == "oaiapp_new"
    assert calls[0]["code_verifier"]
    assert calls[0]["redirect_uri"] == "http://127.0.0.1:4321/auth/callback"
    assert calls[0]["resource"] == ca.RESOURCE
    assert ca.load_credentials().client_id == "oaiapp_new"
    # The pending attempt is single-use.
    assert started["state"] not in ca._pending


def test_complete_login_first_time_requires_issued_client_id(monkeypatch):
    started = ca.begin_login(redirect_uri="http://127.0.0.1:4321/auth/callback")
    _stub_token(monkeypatch, {"access_token": "x", "scope": ca.SCOPES})
    with pytest.raises(ca.ChatGPTAuthError, match="issued client id"):
        ca.complete_login(code="c", state=started["state"], callback_client_id=None)


def test_complete_login_rejects_unknown_state():
    with pytest.raises(ca.ChatGPTAuthError, match="expired"):
        ca.complete_login(code="c", state="nope", callback_client_id="oaiapp_x")


def test_complete_login_rejects_missing_plan_scope(monkeypatch):
    started = ca.begin_login(redirect_uri="http://127.0.0.1:4321/auth/callback")
    _stub_token(monkeypatch, {"access_token": "x", "scope": "openid profile email"})
    _stub_id_token(monkeypatch)
    with pytest.raises(ca.ChatGPTAuthError, match="plan usage was not granted"):
        ca.complete_login(code="c", state=started["state"], callback_client_id="oaiapp_x")
    assert ca.load_credentials() is None


def test_complete_login_reauth_rejects_different_client_or_account(monkeypatch):
    ca.save_credentials(_creds())
    started = ca.begin_login(redirect_uri="http://127.0.0.1:4321/auth/callback")
    with pytest.raises(ca.ChatGPTAuthError, match="different client id"):
        ca.complete_login(code="c", state=started["state"], callback_client_id="oaiapp_other")

    started = ca.begin_login(redirect_uri="http://127.0.0.1:4321/auth/callback")
    _stub_token(monkeypatch, {"access_token": "x", "id_token": "i", "scope": ca.SCOPES})
    _stub_id_token(monkeypatch, sub="someone-else")
    with pytest.raises(ca.ChatGPTAuthError, match="different ChatGPT account"):
        ca.complete_login(code="c", state=started["state"], callback_client_id=None)


# --- access_token / refresh ------------------------------------------------


def test_access_token_returns_cached_when_fresh(monkeypatch):
    ca.save_credentials(_creds(access_token="fresh"))
    monkeypatch.setattr(ca, "_post_token", lambda form: pytest.fail("should not refresh"))
    assert ca.access_token() == "fresh"


def test_access_token_refreshes_when_expiring_and_rotates_refresh_token(monkeypatch):
    ca.save_credentials(_creds(access_token="old", refresh_token="rt-old", expires_at=time.time() + 60))
    calls = _stub_token(
        monkeypatch,
        {"access_token": "new", "refresh_token": "rt-new", "expires_in": 3600, "scope": ca.SCOPES},
    )
    assert ca.access_token() == "new"
    assert calls[0]["grant_type"] == "refresh_token"
    assert calls[0]["refresh_token"] == "rt-old"
    assert calls[0]["client_id"] == "oaiapp_abc"
    assert "scope" not in calls[0]
    saved = ca.load_credentials()
    assert saved.refresh_token == "rt-new"
    assert saved.email == "user@example.com"  # identity carried over


def test_access_token_without_signin_raises():
    with pytest.raises(ca.ChatGPTAuthError, match="Not signed in"):
        ca.access_token()


def test_revoke_and_clear_deletes_file_even_if_openai_unreachable(monkeypatch):
    ca.save_credentials(_creds())

    class _Boom:
        def json(self):
            raise RuntimeError("offline")

    monkeypatch.setattr(ca.httpx, "get", lambda *a, **k: _Boom())
    assert ca.revoke_and_clear() is True
    assert ca.load_credentials() is None


# --- routes ----------------------------------------------------------------


@pytest.fixture
def api(tmp_path: Path, monkeypatch):
    from agent_server.app import create_app

    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        yield client


def test_status_route_reports_disconnected_by_default(api):
    resp = api.get("/v1/auth/chatgpt/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is False
    assert body["planUsage"] is False
    assert body["email"] is None


def test_status_route_reports_connected_and_hides_tokens(api):
    ca.save_credentials(_creds())
    body = api.get("/v1/auth/chatgpt/status").json()
    assert body["connected"] is True
    assert body["email"] == "user@example.com"
    assert "accessToken" not in body and "access_token" not in body


def test_start_route_opens_loopback_listener_and_returns_authorize_url(api):
    import socket

    resp = api.post("/v1/auth/chatgpt/start")
    assert resp.status_code == 200
    body = resp.json()
    assert body["url"].startswith(ca.AUTHORIZE_URL)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(body["url"]).query)
    redirect = q["redirect_uri"][0]
    parsed = urllib.parse.urlparse(redirect)
    assert parsed.hostname == "127.0.0.1" and parsed.path == ca.CALLBACK_PATH
    # The port in redirect_uri is really listening.
    with socket.create_connection(("127.0.0.1", parsed.port), timeout=2):
        pass
    assert body["state"] == q["state"][0]


def test_loopback_callback_completes_login_and_status_poll_sees_it(api, monkeypatch):
    import httpx

    _stub_token(
        monkeypatch,
        {"access_token": "at", "refresh_token": "rt", "id_token": "i", "expires_in": 3600, "scope": ca.SCOPES},
    )
    _stub_id_token(monkeypatch)
    started = api.post("/v1/auth/chatgpt/start").json()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(started["url"]).query)
    redirect = q["redirect_uri"][0]

    # Simulate the browser hitting the loopback with OpenAI's callback params.
    page = httpx.get(
        redirect,
        params={"code": "c-1", "state": started["state"], "client_id": "oaiapp_issued"},
        timeout=5.0,
    )
    assert page.status_code == 200
    assert "Connected to ChatGPT" in page.text
    assert "user@example.com" in page.text

    status = api.get("/v1/auth/chatgpt/status", params={"state": started["state"]}).json()
    assert status["connected"] is True
    assert ca.load_credentials().client_id == "oaiapp_issued"


def test_loopback_callback_access_denied_surfaces_via_status(api):
    import httpx

    started = api.post("/v1/auth/chatgpt/start").json()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(started["url"]).query)
    redirect = q["redirect_uri"][0]
    page = httpx.get(redirect, params={"error": "access_denied", "state": started["state"]}, timeout=5.0)
    assert page.status_code == 200
    assert "cancelled" in page.text.lower()

    resp = api.get("/v1/auth/chatgpt/status", params={"state": started["state"]})
    assert resp.status_code == 400
    assert "did not allow" in resp.json()["detail"]
    assert ca.load_credentials() is None


def test_loopback_callback_wrong_state_is_rejected(api):
    import httpx

    started = api.post("/v1/auth/chatgpt/start").json()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(started["url"]).query)
    redirect = q["redirect_uri"][0]
    page = httpx.get(redirect, params={"code": "c", "state": "wrong"}, timeout=5.0)
    assert page.status_code == 400
    assert ca.load_credentials() is None


def test_logout_route_clears_and_hides_models(api, monkeypatch):
    ca.save_credentials(_creds())
    monkeypatch.setattr(ca, "revoke_and_clear", lambda: ca.clear_credentials())
    body = api.post("/v1/auth/chatgpt/logout").json()
    assert body["connected"] is False
    assert ca.load_credentials() is None


# --- provider wiring -------------------------------------------------------


def test_preflight_requires_signin_and_summary_label():
    from agent.config import Config

    cfg = Config(data={"llm.provider": ca.PROVIDER_KEY, "llm.model": "gpt-5.6-sol"})
    issue = cfg.llm_preflight_issue()
    assert issue and "Continue with ChatGPT" in issue
    ca.save_credentials(_creds())
    assert cfg.llm_preflight_issue() is None
    assert cfg.llm_selection_summary() == "ChatGPT plan · gpt-5.6-sol"


def test_catalog_lists_gpt_models_under_chatgpt_provider():
    from agent.model_catalog import AVAILABLE_MODELS, catalog_provider_for_model

    ids = {mid for mid, _l, _d in AVAILABLE_MODELS[ca.PROVIDER_KEY]}
    assert {"gpt-6-astra", "gpt-5.6-sol", "gpt-5.3-codex"} <= ids
    # Bare GPT ids still default to the API-key provider.
    assert catalog_provider_for_model("gpt-6-astra") == "openai"


def test_models_list_hides_chatgpt_rows_until_connected(tmp_path: Path, monkeypatch):
    from agent.config import Config
    from agent_server.models_service.catalog import list_models

    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    before = {
        m.id for m in list_models(Config.load(), enabled_only=True, discover=False).data
        if m.provider == ca.PROVIDER_KEY
    }
    assert before == set()

    # Connecting must also clear the scoped auto-hides written while
    # disconnected — the callback does this via enable_models_for_provider.
    from agent_server.models_service.mutate import enable_models_for_provider

    ca.save_credentials(_creds())
    cfg = Config.load()
    assert enable_models_for_provider(cfg, ca.PROVIDER_KEY)
    cfg.save()
    after = {
        m.id for m in list_models(Config.load(), enabled_only=True, discover=False).data
        if m.provider == ca.PROVIDER_KEY
    }
    assert "gpt-5.6-sol" in after


def test_chat_model_uses_oauth_token_and_lifts_system_prompt():
    from langchain_core.messages import HumanMessage, SystemMessage

    from agent.deepagents_runtime.chat_model_chatgpt import build_chatgpt_chat_model

    ca.save_credentials(_creds(access_token="oauth-token"))

    class _Cfg:
        def get(self, key, default=None):
            return {
                "llm.model": "gpt-5.6-sol",
                "llm.reasoning_effort": "high",
                "llm.model_reasoning": {},
                "llm.param_heals": {},
            }.get(key, default)

    model = build_chatgpt_chat_model(_Cfg(), temperature=0.3)
    assert model.model_name == "gpt-5.6-sol"
    assert model.openai_api_key.get_secret_value() == "oauth-token"
    assert model.use_responses_api is True
    assert model.store is False
    assert model.temperature is None  # GPT-5 rejects custom temperature
    assert model.reasoning_effort == "high"

    payload = model._get_request_payload(
        [
            SystemMessage(
                content=[{"type": "text", "text": "You are Sandwalk."}],
            ),
            HumanMessage(content="Hi"),
        ]
    )
    assert payload["store"] is False
    assert payload["instructions"] == "You are Sandwalk."
    assert all(item.get("role") != "system" for item in payload["input"])
    assert any(item.get("role") == "user" for item in payload["input"])


def test_friendly_error_maps_plan_limit():
    from agent.runner.usage_ui import UsageUIMixin

    msg = UsageUIMixin._friendly_agent_error("Error 429: chatgpt.tokens.use.direct quota exceeded")
    assert "ChatGPT plan limit reached" in msg
    msg = UsageUIMixin._friendly_agent_error("Not signed in with ChatGPT. Open Dashboard")
    assert "Continue with ChatGPT" in msg
