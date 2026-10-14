"""Sign in with ChatGPT: subscription-backed OAuth for the ``openai-chatgpt`` provider.

OpenAI's open-source flow lets a locally run, open-source tool use the user's
ChatGPT Plus/Pro plan for Responses API calls. No client secret, no API key.
Spec: https://developers.openai.com/siwc/token-sharing-open-source

Credentials live in ``~/.sandwalk/chatgpt-auth.json`` (mode 0600), separate
from ``config.json`` so they never travel with config exports. The file holds
the issued ``client_id``, the per-host ``ext_agent_host_id``, access/refresh/ID
tokens, granted scopes, and the expiry.

Only this module talks to ``auth.openai.com``. Routes call ``begin_login`` /
``complete_login``; the chat-model builder calls ``access_token`` which
refreshes under a file lock when needed.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .constants import CONFIG_DIR, logger

PROVIDER_KEY = "openai-chatgpt"
AGENT_NAME = "Sandwalk"
AUTH_BASE = "https://auth.openai.com"
AUTHORIZE_URL = f"{AUTH_BASE}/api/accounts/authorize"
TOKEN_URL = f"{AUTH_BASE}/api/accounts/oauth/token"
OIDC_CONFIG_URL = f"{AUTH_BASE}/.well-known/openid-configuration"
RESOURCE = "https://api.openai.com/v1"
DYNAMIC_CLIENT_ID = "dynamic_agent_client"
CALLBACK_PATH = "/auth/callback"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = "openid profile email offline_access resource.invoke chatgpt.tokens.use.direct"
# Refresh when this close to expiry so a long turn does not start on a dying token.
REFRESH_SKEW_S = 300
# A pending authorization attempt is discarded after this long.
PENDING_TTL_S = 15 * 60

CREDENTIALS_FILE = CONFIG_DIR / "chatgpt-auth.json"
HOST_ID_FILE = CONFIG_DIR / "chatgpt-host-id"

_refresh_lock = threading.Lock()


class ChatGPTAuthError(RuntimeError):
    """Raised when sign-in, refresh, or token validation fails."""


@dataclass
class ChatGPTCredentials:
    email: str | None
    subject: str
    client_id: str
    ext_agent_host_id: str
    id_token: str | None
    access_token: str
    refresh_token: str | None
    scopes: list[str]
    expires_at: float
    issuer: str = AUTH_BASE
    saved_at: float = field(default_factory=time.time)

    @property
    def plan_usage_granted(self) -> bool:
        return PLAN_SCOPE in self.scopes

    def expires_soon(self, skew_s: float = REFRESH_SKEW_S) -> bool:
        return time.time() >= (self.expires_at - skew_s)

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "issuer": self.issuer,
            "subject": self.subject,
            "client_id": self.client_id,
            "ext_agent_host_id": self.ext_agent_host_id,
            "id_token": self.id_token,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": "Bearer",
            "scopes": list(self.scopes),
            "expires_at": self.expires_at,
            "saved_at": self.saved_at,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> ChatGPTCredentials:
        return cls(
            email=str(raw.get("email") or "") or None,
            subject=str(raw.get("subject") or ""),
            client_id=str(raw.get("client_id") or ""),
            ext_agent_host_id=str(raw.get("ext_agent_host_id") or ""),
            id_token=str(raw.get("id_token") or "") or None,
            access_token=str(raw.get("access_token") or ""),
            refresh_token=str(raw.get("refresh_token") or "") or None,
            scopes=[str(s) for s in (raw.get("scopes") or [])],
            expires_at=float(raw.get("expires_at") or 0),
            issuer=str(raw.get("issuer") or AUTH_BASE),
            saved_at=float(raw.get("saved_at") or 0),
        )


# ---------------------------------------------------------------------------
# Host id + credential file
# ---------------------------------------------------------------------------


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def host_id() -> str:
    """Stable, opaque per-machine id. OpenAI wants ``urn:uuid:`` or a JWK thumbprint."""
    try:
        existing = HOST_ID_FILE.read_text(encoding="utf-8").strip()
        if existing.startswith("urn:uuid:"):
            return existing
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.warning("Could not read ChatGPT host id: %s", exc)
    value = f"urn:uuid:{uuid.uuid4()}"
    try:
        _write_private(HOST_ID_FILE, value + "\n")
    except OSError as exc:
        logger.warning("Could not persist ChatGPT host id: %s", exc)
    return value


def load_credentials() -> ChatGPTCredentials | None:
    try:
        raw = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring unreadable ChatGPT credentials: %s", exc)
        return None
    if not isinstance(raw, dict):
        return None
    creds = ChatGPTCredentials.from_dict(raw)
    if not creds.access_token or not creds.client_id:
        return None
    return creds


def save_credentials(creds: ChatGPTCredentials) -> None:
    _write_private(CREDENTIALS_FILE, json.dumps(creds.to_dict(), indent=2) + "\n")


def clear_credentials() -> bool:
    try:
        CREDENTIALS_FILE.unlink()
        return True
    except FileNotFoundError:
        return False


def is_connected() -> bool:
    creds = load_credentials()
    return bool(creds and creds.plan_usage_granted)


# ---------------------------------------------------------------------------
# PKCE + pending attempts
# ---------------------------------------------------------------------------


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


@dataclass
class PendingLogin:
    state: str
    nonce: str
    verifier: str
    redirect_uri: str
    # Issued client id when reauthorizing; None for first-time registration.
    client_id: str | None
    created_at: float = field(default_factory=time.time)

    def expired(self) -> bool:
        return time.time() - self.created_at > PENDING_TTL_S


_pending: dict[str, PendingLogin] = {}
_pending_lock = threading.Lock()


def _store_pending(item: PendingLogin) -> None:
    with _pending_lock:
        stale = [k for k, v in _pending.items() if v.expired()]
        for key in stale:
            _pending.pop(key, None)
        _pending[item.state] = item


def _take_pending(state: str) -> PendingLogin | None:
    with _pending_lock:
        item = _pending.pop(state, None)
    if item is None or item.expired():
        return None
    return item


def begin_login(*, redirect_uri: str) -> dict[str, str]:
    """Build the authorize URL for a fresh attempt. Returns ``{url, state}``.

    ``redirect_uri`` must be an ``http://127.0.0.1:<port>/auth/callback``
    loopback. The caller owns the listener on that port.
    """
    parsed = urllib.parse.urlparse(redirect_uri)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.path != CALLBACK_PATH:
        raise ChatGPTAuthError(
            f"redirect_uri must be http://127.0.0.1:<port>{CALLBACK_PATH}, got {redirect_uri}"
        )
    existing = load_credentials()
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    params: dict[str, str] = {
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPES,
        "resource": RESOURCE,
        "state": state,
        "nonce": nonce,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "ext_agent_host_id": host_id(),
    }
    if existing and existing.client_id and existing.client_id != DYNAMIC_CLIENT_ID:
        params["client_id"] = existing.client_id
        if existing.id_token:
            params["id_token_hint"] = existing.id_token
        if existing.email:
            params["login_hint"] = existing.email
        pending_client = existing.client_id
    else:
        params["client_id"] = DYNAMIC_CLIENT_ID
        params["agent_name_hint"] = AGENT_NAME
        pending_client = None
    _store_pending(
        PendingLogin(
            state=state,
            nonce=nonce,
            verifier=verifier,
            redirect_uri=redirect_uri,
            client_id=pending_client,
        )
    )
    return {"url": f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}", "state": state}


# ---------------------------------------------------------------------------
# Token exchange / validation
# ---------------------------------------------------------------------------


def _post_token(form: dict[str, str]) -> dict[str, Any]:
    try:
        resp = httpx.post(
            TOKEN_URL,
            data=form,
            headers={"Accept": "application/json", "User-Agent": f"{AGENT_NAME}/1.0"},
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        raise ChatGPTAuthError(f"Could not reach OpenAI auth ({exc.__class__.__name__}).") from exc
    try:
        payload = resp.json()
    except ValueError:
        payload = {}
    if resp.status_code >= 400 or not isinstance(payload, dict):
        err = payload.get("error") if isinstance(payload, dict) else None
        desc = payload.get("error_description") if isinstance(payload, dict) else None
        detail = f"{err}: {desc}" if err and desc else (desc or err or f"HTTP {resp.status_code}")
        raise ChatGPTAuthError(f"OpenAI token endpoint rejected the request ({detail}).")
    return payload


_jwks_cache: dict[str, Any] = {"fetched_at": 0.0, "client": None}


def _jwk_client() -> Any:
    import jwt

    now = time.time()
    client = _jwks_cache.get("client")
    if client is not None and now - float(_jwks_cache["fetched_at"]) < 3600:
        return client
    try:
        cfg = httpx.get(OIDC_CONFIG_URL, timeout=15.0).json()
        jwks_uri = str(cfg.get("jwks_uri") or "")
    except Exception as exc:  # noqa: BLE001
        raise ChatGPTAuthError("Could not load OpenAI OpenID configuration.") from exc
    if not jwks_uri:
        raise ChatGPTAuthError("OpenAI OpenID configuration has no jwks_uri.")
    client = jwt.PyJWKClient(jwks_uri, cache_keys=True)
    _jwks_cache["client"] = client
    _jwks_cache["fetched_at"] = now
    return client


def _validate_id_token(id_token: str, *, client_id: str, nonce: str) -> dict[str, Any]:
    import jwt

    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(id_token)
        claims: dict[str, Any] = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=client_id,
            issuer=AUTH_BASE,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise ChatGPTAuthError(f"OpenAI ID token failed validation ({exc}).") from exc
    if str(claims.get("nonce") or "") != nonce:
        raise ChatGPTAuthError("OpenAI ID token nonce did not match this sign-in attempt.")
    return claims


def complete_login(
    *,
    code: str,
    state: str,
    callback_client_id: str | None,
) -> ChatGPTCredentials:
    """Exchange the authorization code, validate, and persist credentials."""
    pending = _take_pending(state)
    if pending is None:
        raise ChatGPTAuthError("Sign-in attempt expired or was not started here. Try again.")

    if pending.client_id:
        client_id = pending.client_id
        if callback_client_id and callback_client_id != client_id:
            raise ChatGPTAuthError(
                "OpenAI returned a different client id than the saved registration."
            )
    else:
        client_id = str(callback_client_id or "").strip()
        if not client_id or client_id == DYNAMIC_CLIENT_ID:
            raise ChatGPTAuthError("OpenAI did not return an issued client id for this registration.")

    payload = _post_token(
        {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "code_verifier": pending.verifier,
            "redirect_uri": pending.redirect_uri,
            "resource": RESOURCE,
        }
    )
    return _persist_token_response(
        payload,
        client_id=client_id,
        nonce=pending.nonce,
        previous=load_credentials(),
    )


def _persist_token_response(
    payload: dict[str, Any],
    *,
    client_id: str,
    nonce: str | None,
    previous: ChatGPTCredentials | None,
) -> ChatGPTCredentials:
    access_token = str(payload.get("access_token") or "")
    if not access_token:
        raise ChatGPTAuthError("OpenAI token response had no access_token.")
    scopes = str(payload.get("scope") or "").split()
    if PLAN_SCOPE not in scopes:
        raise ChatGPTAuthError(
            "ChatGPT plan usage was not granted. Approve 'Use your ChatGPT plan' when signing in."
        )
    expires_in = float(payload.get("expires_in") or 3600)
    id_token = str(payload.get("id_token") or "") or None

    subject = previous.subject if previous else ""
    email = previous.email if previous else None
    if id_token and nonce is not None:
        claims = _validate_id_token(id_token, client_id=client_id, nonce=nonce)
        subject = str(claims.get("sub") or "")
        email = str(claims.get("email") or "") or None
        if previous and previous.subject and previous.subject != subject:
            raise ChatGPTAuthError(
                "Signed in as a different ChatGPT account. Disconnect first, then sign in again."
            )
    elif not id_token and previous:
        id_token = previous.id_token

    creds = ChatGPTCredentials(
        email=email,
        subject=subject,
        client_id=client_id,
        ext_agent_host_id=host_id(),
        id_token=id_token,
        access_token=access_token,
        refresh_token=str(payload.get("refresh_token") or "") or (previous.refresh_token if previous else None),
        scopes=scopes,
        expires_at=time.time() + expires_in,
    )
    save_credentials(creds)
    return creds


# ---------------------------------------------------------------------------
# Refresh / revoke / access
# ---------------------------------------------------------------------------


def refresh(creds: ChatGPTCredentials) -> ChatGPTCredentials:
    if not creds.refresh_token:
        raise ChatGPTAuthError("No refresh token saved. Sign in with ChatGPT again.")
    payload = _post_token(
        {
            "grant_type": "refresh_token",
            "client_id": creds.client_id,
            "refresh_token": creds.refresh_token,
            "resource": RESOURCE,
        }
    )
    # Refresh responses carry no fresh nonce to check; keep the prior identity.
    return _persist_token_response(payload, client_id=creds.client_id, nonce=None, previous=creds)


def access_token() -> str:
    """Return a valid bearer token, refreshing under a cross-process lock if needed."""
    creds = load_credentials()
    if creds is None:
        raise ChatGPTAuthError("Not signed in with ChatGPT. Open Dashboard → Models to connect.")
    if not creds.plan_usage_granted:
        raise ChatGPTAuthError("ChatGPT plan usage is not enabled for this sign-in.")
    if not creds.expires_soon():
        return creds.access_token
    lock_path = CREDENTIALS_FILE.with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _refresh_lock, open(lock_path, "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            # Another process may have refreshed while we waited.
            latest = load_credentials() or creds
            if not latest.expires_soon():
                return latest.access_token
            return refresh(latest).access_token
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def revoke_and_clear() -> bool:
    """Revoke the refresh token at OpenAI (best effort) and delete the local file."""
    creds = load_credentials()
    if creds and creds.refresh_token:
        try:
            cfg = httpx.get(OIDC_CONFIG_URL, timeout=15.0).json()
            revoke_url = str(cfg.get("revocation_endpoint") or "")
            if revoke_url:
                httpx.post(
                    revoke_url,
                    data={
                        "token": creds.refresh_token,
                        "token_type_hint": "refresh_token",
                        "client_id": creds.client_id,
                    },
                    timeout=15.0,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ChatGPT token revocation failed; clearing locally: %s", exc)
    return clear_credentials()


def status() -> dict[str, Any]:
    """Non-secret summary for the UI."""
    creds = load_credentials()
    if creds is None:
        return {"connected": False, "email": None, "plan_usage": False, "expires_at": None}
    return {
        "connected": creds.plan_usage_granted,
        "email": creds.email,
        "plan_usage": creds.plan_usage_granted,
        "expires_at": creds.expires_at,
    }
