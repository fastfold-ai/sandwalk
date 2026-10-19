"""Unit coverage for ChatGPT auth, competitive landscape, and DESeq2 helpers.

HTTP, token validation, and tabular IO are stubbed or pointed at tmp_path.
Nothing here calls OpenAI, ChatGPT, or a DESeq2 runtime.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from pathlib import Path

import httpx
import pandas as pd
import pytest

import tools.omics  # noqa: F401  (import omics before helpers; avoids a circular import)
from agent.config import chatgpt_auth as ca
from tools.clinical import competitive_landscape
from tools.omics_deseq2_helpers import (
    _build_gene_symbol_mapper,
    _resolve_level_name,
    _resolve_target_gene,
    _target_gene_summary_text,
)

_LOOPBACK = "http://127.0.0.1:4321/auth/callback"


@pytest.fixture(autouse=True)
def _isolated_chatgpt(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(ca, "CREDENTIALS_FILE", tmp_path / "chatgpt-auth.json")
    monkeypatch.setattr(ca, "HOST_ID_FILE", tmp_path / "chatgpt-host-id")
    ca._pending.clear()
    saved_cache = dict(ca._jwks_cache)
    ca._jwks_cache["client"] = None
    ca._jwks_cache["fetched_at"] = 0.0
    yield
    ca._pending.clear()
    ca._jwks_cache.clear()
    ca._jwks_cache.update(saved_cache)


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


def _token_response(status: int, body, *, json_error: bool = False):
    class _Resp:
        status_code = status

        def json(self):
            if json_error:
                raise ValueError("not json")
            return body

    def _post(*_args, **_kwargs):
        return _Resp()

    return _post


# ---------------------------------------------------------------------------
# ChatGPT auth
# ---------------------------------------------------------------------------


def test_credentials_round_trip_partial_payload_and_expiry():
    raw = {
        "email": "",
        "access_token": "tok",
        "client_id": "cid",
        "scopes": ["openid"],
        "expires_at": 0,
    }
    ca.CREDENTIALS_FILE.write_text(json.dumps(raw), encoding="utf-8")
    loaded = ca.load_credentials()
    assert loaded is not None
    assert loaded.email is None
    assert loaded.id_token is None
    assert loaded.refresh_token is None
    assert loaded.issuer == ca.AUTH_BASE
    assert loaded.saved_at == 0
    assert loaded.plan_usage_granted is False
    assert loaded.expires_soon() is True
    assert loaded.to_dict()["token_type"] == "Bearer"

    fresh = _creds(expires_at=time.time() + 100)
    assert fresh.expires_soon(skew_s=300) is True
    assert fresh.expires_soon(skew_s=0) is False
    assert fresh.plan_usage_granted is True


def test_load_credentials_rejects_unreadable_or_incomplete(tmp_path: Path, monkeypatch):
    assert ca.load_credentials() is None
    assert ca.clear_credentials() is False
    assert ca.is_connected() is False
    assert ca.status() == {
        "connected": False,
        "email": None,
        "plan_usage": False,
        "expires_at": None,
    }

    ca.CREDENTIALS_FILE.write_text("{", encoding="utf-8")
    assert ca.load_credentials() is None

    ca.CREDENTIALS_FILE.write_text("[]", encoding="utf-8")
    assert ca.load_credentials() is None

    ca.CREDENTIALS_FILE.write_text(json.dumps({"client_id": "only"}), encoding="utf-8")
    assert ca.load_credentials() is None

    ca.CREDENTIALS_FILE.write_text(json.dumps({"access_token": "only"}), encoding="utf-8")
    assert ca.load_credentials() is None

    blocked = tmp_path / "cred-dir"
    blocked.mkdir()
    monkeypatch.setattr(ca, "CREDENTIALS_FILE", blocked)
    assert ca.load_credentials() is None


def test_host_id_rewrites_non_urn_and_survives_io_errors(tmp_path: Path, monkeypatch):
    assert ca.host_id().startswith("urn:uuid:")
    assert ca.host_id() == ca.HOST_ID_FILE.read_text(encoding="utf-8").strip()

    ca.HOST_ID_FILE.write_text("not-a-urn\n", encoding="utf-8")
    rewritten = ca.host_id()
    assert rewritten.startswith("urn:uuid:")
    assert ca.HOST_ID_FILE.read_text(encoding="utf-8").strip() == rewritten

    blocked = tmp_path / "hostdir"
    blocked.mkdir()
    monkeypatch.setattr(ca, "HOST_ID_FILE", blocked)
    assert ca.host_id().startswith("urn:uuid:")


def test_write_private_unlinks_temp_file_when_write_fails(monkeypatch):
    def fail_fdopen(fd, *_args, **_kwargs):
        os.close(fd)
        raise OSError("disk full")

    monkeypatch.setattr(ca.os, "fdopen", fail_fdopen)
    value = ca.host_id()
    assert value.startswith("urn:uuid:")
    tmp = ca.HOST_ID_FILE.with_suffix(ca.HOST_ID_FILE.suffix + ".tmp")
    assert not tmp.exists()
    assert not ca.HOST_ID_FILE.exists()


def test_pending_login_drops_stale_and_expired_attempts():
    stale = ca.PendingLogin(
        state="old",
        nonce="n",
        verifier="v",
        redirect_uri=_LOOPBACK,
        client_id=None,
        created_at=time.time() - ca.PENDING_TTL_S - 5,
    )
    ca._pending["old"] = stale
    fresh = ca.PendingLogin(
        state="new",
        nonce="n2",
        verifier="v2",
        redirect_uri=_LOOPBACK,
        client_id="oaiapp_abc",
    )
    ca._store_pending(fresh)
    assert "old" not in ca._pending
    assert ca._take_pending("missing") is None
    assert ca._take_pending("new") is fresh

    expired = ca.PendingLogin(
        state="aged",
        nonce="n",
        verifier="v",
        redirect_uri=_LOOPBACK,
        client_id=None,
        created_at=time.time() - ca.PENDING_TTL_S - 1,
    )
    ca._pending["aged"] = expired
    assert expired.expired() is True
    assert ca._take_pending("aged") is None
    assert "aged" not in ca._pending


def test_begin_login_rejects_non_loopback_and_reuses_or_registers():
    with pytest.raises(ca.ChatGPTAuthError, match="redirect_uri"):
        ca.begin_login(redirect_uri="https://evil.example/auth/callback")

    ca.save_credentials(_creds(email=None, id_token=None))
    hinted = urllib.parse.parse_qs(urllib.parse.urlparse(ca.begin_login(redirect_uri=_LOOPBACK)["url"]).query)
    assert hinted["client_id"] == ["oaiapp_abc"]
    assert "id_token_hint" not in hinted
    assert "login_hint" not in hinted
    assert ca._pending[hinted["state"][0]].client_id == "oaiapp_abc"

    ca.save_credentials(_creds(client_id=ca.DYNAMIC_CLIENT_ID))
    dynamic = urllib.parse.parse_qs(urllib.parse.urlparse(ca.begin_login(redirect_uri=_LOOPBACK)["url"]).query)
    assert dynamic["client_id"] == [ca.DYNAMIC_CLIENT_ID]
    assert dynamic["agent_name_hint"] == [ca.AGENT_NAME]
    assert ca._pending[dynamic["state"][0]].client_id is None


def test_post_token_success_and_transport_failures(monkeypatch):
    monkeypatch.setattr(
        ca.httpx,
        "post",
        _token_response(200, {"access_token": "ok", "token_type": "Bearer"}),
    )
    assert ca._post_token({"grant_type": "authorization_code"})["access_token"] == "ok"

    monkeypatch.setattr(ca.httpx, "post", _token_response(200, None, json_error=True))
    assert ca._post_token({"grant_type": "refresh_token"}) == {}

    def explode(*_args, **_kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(ca.httpx, "post", explode)
    with pytest.raises(ca.ChatGPTAuthError, match="ConnectError") as exc:
        ca._post_token({"grant_type": "refresh_token"})
    assert exc.value.title == "Sign-in failed"


@pytest.mark.parametrize(
    ("status", "body", "grant", "match", "title"),
    [
        (400, {"error": "invalid_grant"}, "authorization_code", "Plus, Pro", "ChatGPT plan needed"),
        (400, {"error": "invalid_grant", "error_description": "code expired"}, "authorization_code", "expired", "Sign-in failed"),
        (400, {"error": "invalid_grant", "error_description": "already used"}, "authorization_code", "already used", "Sign-in failed"),
        (400, {"error": "invalid_grant"}, "refresh_token", "Sign in again", "Sign-in expired"),
        (400, {"error": "invalid_request", "error_description": "bad redirect"}, "authorization_code", "invalid_request: bad redirect", "Sign-in failed"),
        (400, {"error_description": "nope"}, "authorization_code", "nope", "Sign-in failed"),
        (502, {"error": "server_error"}, "authorization_code", "server_error", "Sign-in failed"),
        (503, {"error": 12, "error_description": {"x": 1}}, "authorization_code", "HTTP 503", "Sign-in failed"),
        (200, ["not", "a", "dict"], "authorization_code", "HTTP 200", "Sign-in failed"),
    ],
)
def test_post_token_maps_endpoint_errors(monkeypatch, status, body, grant, match, title):
    monkeypatch.setattr(ca.httpx, "post", _token_response(status, body))
    with pytest.raises(ca.ChatGPTAuthError, match=match) as exc:
        ca._post_token({"grant_type": grant})
    assert exc.value.title == title


def test_jwk_client_caches_refetches_and_rejects_bad_discovery(monkeypatch):
    import jwt

    calls = {"n": 0}

    class _Resp:
        def json(self):
            return {"jwks_uri": "https://auth.example/jwks"}

    def _get(url, timeout=0):
        calls["n"] += 1
        assert url == ca.OIDC_CONFIG_URL
        assert timeout == 15.0
        return _Resp()

    created: list[tuple[str, bool]] = []

    class _FakeJWK:
        def __init__(self, uri, cache_keys=False):
            created.append((uri, cache_keys))

    monkeypatch.setattr(ca.httpx, "get", _get)
    monkeypatch.setattr(jwt, "PyJWKClient", _FakeJWK)
    first = ca._jwk_client()
    second = ca._jwk_client()
    assert first is second
    assert calls["n"] == 1
    assert created == [("https://auth.example/jwks", True)]

    ca._jwks_cache["fetched_at"] = 0.0
    third = ca._jwk_client()
    assert third is not first
    assert calls["n"] == 2

    def _down(*_args, **_kwargs):
        raise httpx.ConnectError("no")

    ca._jwks_cache["client"] = None
    ca._jwks_cache["fetched_at"] = 0.0
    monkeypatch.setattr(ca.httpx, "get", _down)
    with pytest.raises(ca.ChatGPTAuthError, match="OpenID configuration"):
        ca._jwk_client()

    class _Empty:
        def json(self):
            return {}

    def _empty_config(*_args, **_kwargs):
        return _Empty()

    monkeypatch.setattr(ca.httpx, "get", _empty_config)
    with pytest.raises(ca.ChatGPTAuthError, match="jwks_uri"):
        ca._jwk_client()


def test_validate_id_token_nonce_and_jwt_errors(monkeypatch):
    import jwt

    class _Signing:
        key = "secret"

    class _Client:
        def get_signing_key_from_jwt(self, token):
            assert token == "header.payload.sig"
            return _Signing()

    def _client():
        return _Client()

    seen = {}

    def _decode(token, key, *, algorithms, audience, issuer, options):
        seen["args"] = (token, key, algorithms, audience, issuer, options)
        return {"nonce": "nonce-1", "sub": "sub"}

    monkeypatch.setattr(ca, "_jwk_client", _client)
    monkeypatch.setattr(jwt, "decode", _decode)
    claims = ca._validate_id_token("header.payload.sig", client_id="cid", nonce="nonce-1")
    assert claims["sub"] == "sub"
    assert seen["args"][1] == "secret"
    assert seen["args"][2] == ["RS256", "ES256"]
    assert seen["args"][3] == "cid"
    assert seen["args"][4] == ca.AUTH_BASE

    def _wrong_nonce(*_args, **_kwargs):
        return {"nonce": "other"}

    monkeypatch.setattr(jwt, "decode", _wrong_nonce)
    with pytest.raises(ca.ChatGPTAuthError, match="nonce"):
        ca._validate_id_token("header.payload.sig", client_id="cid", nonce="nonce-1")

    def _bad_sig(*_args, **_kwargs):
        raise jwt.InvalidTokenError("bad sig")

    monkeypatch.setattr(jwt, "decode", _bad_sig)
    with pytest.raises(ca.ChatGPTAuthError, match="failed validation"):
        ca._validate_id_token("header.payload.sig", client_id="cid", nonce="nonce-1")


def test_complete_login_reauth_success_mismatch_and_expiry(monkeypatch):
    ca.save_credentials(_creds())
    started = ca.begin_login(redirect_uri=_LOOPBACK)

    def _should_not_post(_form):
        raise AssertionError("token endpoint should not be called")

    monkeypatch.setattr(ca, "_post_token", _should_not_post)
    with pytest.raises(ca.ChatGPTAuthError, match="different client id"):
        ca.complete_login(code="c", state=started["state"], callback_client_id="other")

    started = ca.begin_login(redirect_uri=_LOOPBACK)
    posted = {}

    def _post(form):
        posted["form"] = form
        return {
            "access_token": "new-at",
            "refresh_token": "new-rt",
            "id_token": "new-id",
            "expires_in": 120,
            "scope": ca.SCOPES,
        }

    def _validate(id_token, *, client_id, nonce):
        assert id_token == "new-id"
        assert client_id == "oaiapp_abc"
        assert nonce
        return {"sub": "sub-1", "email": "user@example.com"}

    monkeypatch.setattr(ca, "_post_token", _post)
    monkeypatch.setattr(ca, "_validate_id_token", _validate)
    creds = ca.complete_login(code="abc", state=started["state"], callback_client_id=None)
    assert creds.access_token == "new-at"
    assert posted["form"]["client_id"] == "oaiapp_abc"
    assert posted["form"]["code"] == "abc"

    started = ca.begin_login(redirect_uri=_LOOPBACK)
    ca._pending[started["state"]].created_at = time.time() - ca.PENDING_TTL_S - 5
    with pytest.raises(ca.ChatGPTAuthError, match="expired"):
        ca.complete_login(code="c", state=started["state"], callback_client_id="oaiapp_abc")


def test_complete_login_first_registration_strips_client_id(monkeypatch):
    started = ca.begin_login(redirect_uri=_LOOPBACK)
    with pytest.raises(ca.ChatGPTAuthError, match="issued client id"):
        ca.complete_login(code="c", state=started["state"], callback_client_id="   ")

    started = ca.begin_login(redirect_uri=_LOOPBACK)
    with pytest.raises(ca.ChatGPTAuthError, match="issued client id"):
        ca.complete_login(code="c", state=started["state"], callback_client_id=ca.DYNAMIC_CLIENT_ID)

    started = ca.begin_login(redirect_uri=_LOOPBACK)

    def _post(_form):
        return {"access_token": "at", "id_token": "idt", "expires_in": 30, "scope": ca.SCOPES}

    def _validate(id_token, *, client_id, nonce):
        return {"sub": "person", "email": "new@example.com", "nonce": nonce}

    monkeypatch.setattr(ca, "_post_token", _post)
    monkeypatch.setattr(ca, "_validate_id_token", _validate)
    creds = ca.complete_login(code="c", state=started["state"], callback_client_id="  oaiapp_new  ")
    assert creds.client_id == "oaiapp_new"
    assert creds.email == "new@example.com"
    assert creds.subject == "person"


def test_persist_token_response_identity_edges(monkeypatch):
    with pytest.raises(ca.ChatGPTAuthError, match="no access_token"):
        ca._persist_token_response({}, client_id="cid", nonce=None, previous=None)
    with pytest.raises(ca.ChatGPTAuthError, match="plan usage was not granted"):
        ca._persist_token_response(
            {"access_token": "a", "scope": "openid"},
            client_id="cid",
            nonce=None,
            previous=None,
        )

    previous = _creds(id_token="keep-id", refresh_token="keep-rt", subject="", email="old@example.com")

    def _empty_email(id_token, *, client_id, nonce):
        return {"sub": "brand-new", "email": ""}

    monkeypatch.setattr(ca, "_validate_id_token", _empty_email)
    switched = ca._persist_token_response(
        {"access_token": "a2", "id_token": "idt", "scope": ca.SCOPES, "expires_in": 10},
        client_id="cid",
        nonce="n",
        previous=previous,
    )
    assert switched.subject == "brand-new"
    assert switched.email is None
    assert switched.refresh_token == "keep-rt"

    def _other_account(id_token, *, client_id, nonce):
        return {"sub": "someone-else", "email": "x@example.com"}

    monkeypatch.setattr(ca, "_validate_id_token", _other_account)
    with pytest.raises(ca.ChatGPTAuthError, match="different ChatGPT account"):
        ca._persist_token_response(
            {"access_token": "a3", "id_token": "idt", "scope": ca.SCOPES},
            client_id="cid",
            nonce="n",
            previous=_creds(subject="sub-1"),
        )


def test_refresh_keeps_identity_and_requires_refresh_token(monkeypatch):
    with pytest.raises(ca.ChatGPTAuthError, match="No refresh token"):
        ca.refresh(_creds(refresh_token=None))

    def _post(form):
        assert form["grant_type"] == "refresh_token"
        assert form["refresh_token"] == "refresh-1"
        return {"access_token": "rotated", "scope": ca.SCOPES}

    monkeypatch.setattr(ca, "_post_token", _post)
    kept = ca.refresh(_creds())
    assert kept.access_token == "rotated"
    assert kept.refresh_token == "refresh-1"
    assert kept.id_token == "id.tok.en"
    assert kept.email == "user@example.com"

    def _post_with_id(form):
        return {
            "access_token": "rotated-2",
            "id_token": "fresh-id",
            "refresh_token": "rt-2",
            "scope": ca.SCOPES,
        }

    monkeypatch.setattr(ca, "_post_token", _post_with_id)
    rotated = ca.refresh(_creds())
    assert rotated.id_token == "fresh-id"
    assert rotated.refresh_token == "rt-2"
    assert rotated.subject == "sub-1"


def test_access_token_plan_gate_and_locked_refresh(monkeypatch):
    with pytest.raises(ca.ChatGPTAuthError, match="Not signed in"):
        ca.access_token()

    ca.save_credentials(_creds(access_token="fresh-now", expires_at=time.time() + 5000))
    assert ca.access_token() == "fresh-now"

    ca.save_credentials(_creds(scopes=["openid"], expires_at=time.time() + 5000))
    with pytest.raises(ca.ChatGPTAuthError, match="plan usage is not enabled"):
        ca.access_token()

    stale = _creds(access_token="stale", expires_at=time.time() + 30)
    fresh = _creds(access_token="from-peer", expires_at=time.time() + 8000)
    seen = {"n": 0}

    def _load_then_fresh():
        seen["n"] += 1
        return stale if seen["n"] == 1 else fresh

    def _no_refresh(_creds_arg):
        raise AssertionError("peer already refreshed")

    monkeypatch.setattr(ca, "load_credentials", _load_then_fresh)
    monkeypatch.setattr(ca, "refresh", _no_refresh)
    assert ca.access_token() == "from-peer"

    def _always_stale():
        return stale

    def _do_refresh(_creds_arg):
        return _creds(access_token="rotated", expires_at=time.time() + 9000)

    monkeypatch.setattr(ca, "load_credentials", _always_stale)
    monkeypatch.setattr(ca, "refresh", _do_refresh)
    assert ca.access_token() == "rotated"


def test_revoke_and_status(monkeypatch):
    assert ca.revoke_and_clear() is False

    ca.save_credentials(_creds(refresh_token=None))
    assert ca.revoke_and_clear() is True
    assert ca.load_credentials() is None

    ca.save_credentials(_creds())
    posted = {}

    class _Cfg:
        def json(self):
            return {"revocation_endpoint": "https://auth.example/revoke"}

    def _get(*_args, **_kwargs):
        return _Cfg()

    def _post(url, data=None, timeout=None, **_kwargs):
        posted["url"] = url
        posted["data"] = data
        posted["timeout"] = timeout
        return object()

    monkeypatch.setattr(ca.httpx, "get", _get)
    monkeypatch.setattr(ca.httpx, "post", _post)
    assert ca.revoke_and_clear() is True
    assert posted["url"] == "https://auth.example/revoke"
    assert posted["data"]["token"] == "refresh-1"
    assert posted["data"]["client_id"] == "oaiapp_abc"
    assert ca.load_credentials() is None

    ca.save_credentials(_creds())

    class _NoEndpoint:
        def json(self):
            return {}

    def _no_endpoint(*_args, **_kwargs):
        return _NoEndpoint()

    monkeypatch.setattr(ca.httpx, "get", _no_endpoint)
    assert ca.revoke_and_clear() is True

    ca.save_credentials(_creds())

    def _boom(*_args, **_kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(ca.httpx, "get", _boom)
    assert ca.revoke_and_clear() is True
    assert ca.status()["connected"] is False

    ca.save_credentials(_creds())
    summary = ca.status()
    assert summary["connected"] is True
    assert summary["email"] == "user@example.com"
    assert summary["plan_usage"] is True
    assert "access_token" not in summary


# ---------------------------------------------------------------------------
# clinical.competitive_landscape
# ---------------------------------------------------------------------------


def _install_clinical(monkeypatch, trial_result, handler):
    def trial_search(query="", **_kwargs):
        trial_search.queries.append(query)
        return trial_result

    trial_search.queries = []

    def request_json(method, url, **kwargs):
        request_json.calls.append((method, url, kwargs))
        return handler(method, url, kwargs)

    request_json.calls = []
    monkeypatch.setattr("tools.clinical.trial_search", trial_search)
    monkeypatch.setattr("tools.clinical.request_json", request_json)
    return trial_search, request_json


def _error_handler(message):
    def handler(_method, _url, _kwargs):
        return ({}, message)

    return handler


def test_competitive_landscape_aggregates_trials_chembl_and_open_targets(monkeypatch):
    trials = [{"nct_id": f"NCT{i}"} for i in range(11)]
    activities = [
        {"molecule_chembl_id": "", "assay_description": "ignore me"},
        {
            "molecule_chembl_id": "M0",
            "molecule_pref_name": "",
            "standard_type": "IC50",
            "standard_value": "1",
            "standard_units": "nM",
            "pchembl_value": 8.1,
            "assay_description": "Inhibit degrad agonist antagonist allosteric antibody covalent",
        },
        {"molecule_chembl_id": "M0", "molecule_pref_name": "duplicate"},
    ]
    for idx in range(1, 16):
        activities.append(
            {
                "molecule_chembl_id": f"M{idx}",
                "molecule_pref_name": f"Compound {idx}",
                "standard_type": "Ki",
                "standard_value": idx,
                "standard_units": "nM",
                "pchembl_value": None,
            }
        )

    ot_rows = []
    for idx in range(21):
        ot_rows.append(
            {
                "prefName": f"Drug{idx}",
                "drugId": f"CHEMBL{idx}",
                "drugType": "Small molecule",
                "mechanismOfAction": "Inhibitor" if idx % 2 == 0 else "",
                "phase": 0 if idx == 0 else 2,
                "status": "Approved",
                "disease": {"id": "EFO_1", "name": "Melanoma"},
            }
        )
    ot_rows.append(
        {
            "prefName": "",
            "drugId": "CHEMBLSKIP",
            "drugType": "Antibody",
            "mechanismOfAction": "PROTAC",
            "phase": 3,
            "status": "Terminated",
            "disease": {"name": "Lung cancer"},
        }
    )
    ot_rows.append(
        {
            "prefName": "NoDisease",
            "drugId": "CHEMBLND",
            "drugType": "Unknown",
            "mechanismOfAction": "Agonist",
            "phase": None,
            "status": "",
            "disease": None,
        }
    )

    def handler(method, url, kwargs):
        if url.endswith("target/search.json"):
            assert kwargs["params"]["q"] == "BRAF"
            return (
                {
                    "targets": [
                        {
                            "organism": "Mus musculus",
                            "target_type": "SINGLE PROTEIN",
                            "target_chembl_id": "MOUSE",
                        },
                        {
                            "organism": "Homo sapiens",
                            "target_type": "PROTEIN COMPLEX",
                            "target_chembl_id": "COMPLEX",
                        },
                        {
                            "organism": "Homo sapiens",
                            "target_type": "SINGLE PROTEIN",
                            "target_chembl_id": "HUMAN",
                        },
                    ]
                },
                None,
            )
        if url.endswith("activity.json"):
            assert kwargs["params"]["target_chembl_id"] == "HUMAN"
            return ({"activities": activities}, None)
        query = kwargs.get("json", {}).get("query", "")
        if "knownDrugs" in query:
            assert kwargs["json"]["variables"]["ensemblId"] == "ENSG00000157764"
            return (
                {
                    "data": {
                        "target": {
                            "knownDrugs": {
                                "uniqueDrugs": 40,
                                "rows": ot_rows,
                            }
                        }
                    }
                },
                None,
            )
        return (
            {
                "data": {
                    "search": {
                        "hits": [
                            {"entity": "disease", "id": "EFO_1", "name": "melanoma"},
                            {"entity": "target", "id": "ENSG00000157764", "name": "BRAF"},
                        ]
                    }
                }
            },
            None,
        )

    trial_search, _request = _install_clinical(
        monkeypatch,
        {
            "total_count": 42,
            "phase_distribution": {"PHASE3": 1, "PHASE2": 3},
            "status_distribution": {"RECRUITING": 4},
            "trials": trials,
        },
        handler,
    )
    result = competitive_landscape(gene="BRAF", indication="melanoma")
    assert trial_search.queries == ["BRAF melanoma"]
    assert result["indication"] == "melanoma"
    assert result["trials"]["total_count"] == 42
    assert len(result["trials"]["top_trials"]) == 10
    assert result["chembl"]["target_chembl_id"] == "HUMAN"
    assert result["chembl"]["unique_compounds"] == 16
    assert result["chembl"]["top_compounds"][0]["name"] == "M0"
    assert len(result["chembl"]["top_compounds"]) == 15
    assert result["chembl"]["moa_types"] == [
        "Agonist",
        "Allosteric modulator",
        "Antagonist",
        "Antibody",
        "Covalent binder",
        "Degrader",
        "Inhibitor",
    ]
    assert result["open_targets"]["ensembl_id"] == "ENSG00000157764"
    assert result["open_targets"]["unique_drugs"] == 40
    assert len(result["open_targets"]["drugs"]) == 20
    assert result["open_targets"]["drugs"][0]["drug"] == "Drug0"
    assert "CHEMBLSKIP" not in {row["drug"] for row in result["open_targets"]["drugs"]}
    assert result["open_targets"]["phase_distribution"]["Phase 2"] == 20
    assert result["open_targets"]["phase_distribution"]["Unknown"] == 2
    assert result["open_targets"]["mechanisms"] == ["Agonist", "Inhibitor"]
    assert "in melanoma" in result["summary"]
    assert "PHASE2: 3, PHASE3: 1" in result["summary"]
    assert "Clinical trials: 42" in result["summary"]
    assert "ChEMBL compounds: 16" in result["summary"]
    assert "Open Targets known drugs: 40" in result["summary"]


def test_competitive_landscape_falls_back_when_sources_miss(monkeypatch):
    def handler(method, url, kwargs):
        if url.endswith("target/search.json"):
            return (
                {
                    "targets": [
                        {"organism": "Mus musculus", "target_type": "ORGANISM", "target_chembl_id": "MOUSE"},
                        {"organism": "Homo sapiens", "target_type": "CELL-LINE"},
                    ]
                },
                None,
            )
        if url.endswith("activity.json"):
            assert kwargs["params"]["target_chembl_id"] == "MOUSE"
            return ({}, None)
        return ({"data": {"search": {"hits": [{"entity": "study", "id": "S1"}]}}}, None)

    _install_clinical(
        monkeypatch,
        {"error": "ctgov unavailable"},
        handler,
    )
    result = competitive_landscape("EGFR")
    assert result["indication"] == "all"
    assert result["trials"] == {"error": "ctgov unavailable", "total_count": 0}
    assert result["chembl"]["target_chembl_id"] == "MOUSE"
    assert result["chembl"]["unique_compounds"] == 0
    assert result["chembl"]["moa_types"] == []
    assert "Could not resolve Ensembl ID" in result["open_targets"]["error"]
    assert "Competitive landscape for EGFR:" in result["summary"]
    assert "(none)" in result["summary"]
    assert "not characterized" in result["summary"]


def test_competitive_landscape_reports_query_failures(monkeypatch):
    def handler(method, url, kwargs):
        if "chembl" in url and url.endswith("target/search.json"):
            return ({}, "target down")
        if "opentargets" in url:
            query = kwargs.get("json", {}).get("query", "")
            if "knownDrugs" in query:
                return ({}, "drugs down")
            return (
                {"data": {"search": {"hits": [{"entity": "target", "id": "ENSG1"}]}}},
                None,
            )
        return ({}, "unexpected")

    _install_clinical(monkeypatch, {"total_count": 0, "trials": []}, handler)
    chembl_fail = competitive_landscape("BRAF", indication="melanoma")
    assert "ChEMBL query failed: target down" in chembl_fail["chembl"]["error"]
    assert "Open Targets query failed: drugs down" in chembl_fail["open_targets"]["error"]

    def search_down(_method, url, _kwargs):
        if "chembl" in url:
            return ({"targets": []}, None)
        if "opentargets" in url:
            return ({}, "search down")
        return ({}, "unexpected")

    _install_clinical(monkeypatch, {"total_count": 0, "trials": []}, search_down)
    search_fail = competitive_landscape("KRAS")
    assert "Open Targets query failed: search down" in search_fail["open_targets"]["error"]

    def no_target(_method, url, kwargs):
        if url.endswith("target/search.json"):
            return ({"targets": []}, None)
        query = kwargs.get("json", {}).get("query", "")
        if "knownDrugs" in query:
            return ({"data": {"target": {}}}, None)
        return ({"data": {"search": {"hits": [{"entity": "target", "id": "ENSG9"}]}}}, None)

    _install_clinical(monkeypatch, {"total_count": 1, "phase_distribution": {}, "trials": []}, no_target)
    missing = competitive_landscape("NONE")
    assert missing["chembl"]["error"] == "No ChEMBL target found for NONE"
    assert missing["open_targets"]["error"] == "No known drugs found"

    def explode(_method, url, _kwargs):
        if "chembl" in url:
            raise RuntimeError("timeout")
        raise RuntimeError("socket")

    _install_clinical(monkeypatch, {"total_count": 0, "trials": []}, explode)
    blown = competitive_landscape("TP53")
    assert "ChEMBL query failed: timeout" in blown["chembl"]["error"]
    assert "Open Targets query failed: socket" in blown["open_targets"]["error"]

    def activity_down(_method, url, _kwargs):
        if url.endswith("target/search.json"):
            return (
                {
                    "targets": [
                        {
                            "organism": "Homo sapiens",
                            "target_type": "SINGLE PROTEIN",
                            "target_chembl_id": "C1",
                        }
                    ]
                },
                None,
            )
        if url.endswith("activity.json"):
            return ({}, "activity down")
        return ({"data": {"search": {"hits": []}}}, None)

    _install_clinical(monkeypatch, {"total_count": 0, "trials": []}, activity_down)
    activity = competitive_landscape("ALK")
    assert "activity down" in activity["chembl"]["error"]


def test_competitive_landscape_without_httpx(monkeypatch):
    import builtins
    import sys

    real_import = builtins.__import__
    saved = sys.modules.get("httpx")
    sys.modules.pop("httpx", None)

    def blocked(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "httpx":
            raise ImportError("httpx blocked for test")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked)
    try:
        result = competitive_landscape("EGFR")
    finally:
        if saved is not None:
            sys.modules["httpx"] = saved
    assert result["error"] == "httpx required (pip install httpx)"
    assert result["summary"] == "httpx required (pip install httpx)"


# ---------------------------------------------------------------------------
# omics DESeq2 helpers
# ---------------------------------------------------------------------------


def _results_frame():
    return pd.DataFrame(
        {
            "log2FoldChange": [1.5, float("nan"), 0.0],
            "baseMean": [10.0, float("nan"), 2.0],
            "padj": [0.01, float("nan"), 0.2],
            "pvalue": [0.001, float("nan"), 0.0],
        },
        index=["ENSG0001.3", "ENSG0002", "GENE0"],
    )


def test_resolve_level_name_exact_normalized_and_shorthand():
    assert _resolve_level_name("", ["A", "B"]) == ""
    assert _resolve_level_name("Control", ["Control", "Treat"]) == "Control"
    assert _resolve_level_name("???", ["A"]) == "???"
    assert _resolve_level_name("C.B.D", ["CBD", "OTHER"]) == "CBD"
    assert _resolve_level_name("CBD", ["AAA", "CBD_IC50"]) == "CBD_IC50"
    assert _resolve_level_name("IC50", ["drug_IC50_nM"]) == "drug_IC50_nM"
    assert _resolve_level_name("ZZZ", ["AAA"]) == "ZZZ"
    assert _resolve_level_name("A-B", ["A_B", "AB"]) == "A-B"

    chosen = _resolve_level_name(
        "CBD",
        ["CBD_serum_starvation", "CBD_cisplatin", "CBD_combo", "CBD_plus", "CBD_plain"],
    )
    assert chosen == "CBD_plain"
    assert _resolve_level_name("CBD", ["CBD_a", "CBD_b"]) == "CBD"


def test_build_gene_symbol_mapper_column_fallbacks():
    explicit = pd.DataFrame({"gid": ["ENSG1.5", None], "sym": ["TP53", "BRCA1"]})
    assert _build_gene_symbol_mapper(explicit, "gid", "sym") == {"tp53": "ENSG1"}

    defaults = pd.DataFrame(
        {"ENSG_ID": ["ENSG2.1", "ENSG3"], "gene_name": ["EGFR", ""]}
    )
    assert _build_gene_symbol_mapper(defaults, "", "") == {"egfr": "ENSG2"}

    symbol_col = pd.DataFrame({"ENSG_ID": ["ENSG4"], "symbol": ["MYC"]})
    assert _build_gene_symbol_mapper(symbol_col, "", "") == {"myc": "ENSG4"}

    positional = pd.DataFrame({"id": ["ENSG5.2"], "label": ["ALK"]})
    assert _build_gene_symbol_mapper(positional, "", "") == {"alk": "ENSG5"}


def test_resolve_target_gene_by_id_and_summary_text():
    frame = _results_frame()
    assert _resolve_target_gene(frame, "  ", "counts.csv", "", "", "") is None

    exact = _resolve_target_gene(frame, "ensg0001.3", "counts.csv", "", "", "")
    assert exact["found"] is True
    assert exact["matched_gene_id"] == "ENSG0001.3"
    assert exact["log2FoldChange"] == 1.5
    assert exact["pvalue"] == 0.001

    versionless = _resolve_target_gene(frame, "ENSG0001", "counts.csv", "", "", "")
    assert versionless["matched_gene_id"] == "ENSG0001.3"

    missing_stats = _resolve_target_gene(frame, "ENSG0002", "counts.csv", "", "", "")
    assert missing_stats["found"] is True
    assert missing_stats["log2FoldChange"] is None
    assert missing_stats["baseMean"] is None
    assert missing_stats["padj"] is None
    assert missing_stats["pvalue"] is None

    no_pvalue = pd.DataFrame(
        {"log2FoldChange": [2.5], "baseMean": [3.0], "padj": [0.04]},
        index=["GENE9"],
    )
    resolved = _resolve_target_gene(no_pvalue, "GENE9", "counts.csv", "", "", "")
    assert resolved["pvalue"] is None
    assert resolved["log2FoldChange"] == 2.5

    assert _resolve_target_gene(frame, "NOPE", "counts.csv", "", "", "") == {
        "target_gene": "NOPE",
        "found": False,
    }

    assert _target_gene_summary_text(None, "TP53") == ""
    assert _target_gene_summary_text({}, "TP53") == ""
    assert _target_gene_summary_text({"found": True, "log2FoldChange": 1.5}, "TP53") == (
        " TP53 log2FoldChange=1.5."
    )
    assert _target_gene_summary_text({"found": True, "log2FoldChange": None}, "TP53") == (
        " TP53 log2FoldChange=NA."
    )
    assert _target_gene_summary_text({"found": False}, "TP53") == " TP53 was not found in result gene IDs."


def test_resolve_target_gene_uses_gene_map_and_auto_discovery(tmp_path: Path, monkeypatch):
    frame = pd.DataFrame(
        {"log2FoldChange": [0.5], "baseMean": [4.0], "padj": [0.2], "pvalue": [0.1]},
        index=["ENSG0009.1"],
    )
    gene_map = tmp_path / "map.csv"
    pd.DataFrame({"gid": ["ENSG0009.4"], "sym": ["Myc"]}).to_csv(gene_map, index=False)
    mapped = _resolve_target_gene(frame, "myc", str(tmp_path / "counts.csv"), str(gene_map), "gid", "sym")
    assert mapped["found"] is True
    assert mapped["matched_gene_id"] == "ENSG0009.1"

    missing_map = _resolve_target_gene(
        frame, "TP53", str(tmp_path / "counts.csv"), str(tmp_path / "absent.csv"), "", ""
    )
    assert missing_map["found"] is False

    empty_map = tmp_path / "empty.csv"
    pd.DataFrame(columns=["ENSG_ID", "gene_name"]).to_csv(empty_map, index=False)
    assert _resolve_target_gene(frame, "TP53", "counts.csv", str(empty_map), "", "")["found"] is False

    other = tmp_path / "other.csv"
    pd.DataFrame({"ENSG_ID": ["ENSG1"], "gene_name": ["BRCA1"]}).to_csv(other, index=False)
    assert _resolve_target_gene(frame, "TP53", "counts.csv", str(other), "", "")["found"] is False

    capsule = tmp_path / "capsule"
    capsule.mkdir()
    counts = capsule / "counts.csv"
    counts.write_text("id,s1\nG1,1\n", encoding="utf-8")
    (capsule / "gene_meta.csv").mkdir()
    (capsule / "gene_meta.md").write_text("skip", encoding="utf-8")
    (capsule / "plain.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (capsule / "gene_only.csv").write_text("ENSG_ID,gene_name\nE1,TP53\n", encoding="utf-8")
    (capsule / "aaa_gene_meta.xlsx").write_bytes(b"not a workbook")
    pd.DataFrame({"ENSG_ID": ["ENSG1"], "gene_name": [""]}).to_csv(capsule / "mmm_gene_meta.csv", index=False)
    pd.DataFrame({"ENSG_ID": ["ENSG0009"], "gene_name": ["TP53"]}).to_csv(
        capsule / "zzz_gene_annot.tsv", sep="\t", index=False
    )
    discovered = _resolve_target_gene(frame, "TP53", str(counts), "", "", "")
    assert discovered["found"] is True
    assert discovered["matched_gene_id"] == "ENSG0009.1"

    def _explode(self):
        raise OSError("denied")

    monkeypatch.setattr(Path, "iterdir", _explode)
    failed = _resolve_target_gene(frame, "TP53", str(counts), "", "", "")
    assert failed == {"target_gene": "TP53", "found": False}
