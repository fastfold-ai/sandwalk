"""Coverage for doctor HTTP probes and catalog MCP checks.

Network, AWS, and the MCP store are mocked. No source modules are patched
except through pytest's monkeypatch, and only for the duration of each test.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

from agent.config import OPENAI_COMPATIBLE_PROVIDERS
from agent.config.chatgpt_auth import ChatGPTAuthError
from agent.doctor.checks_mcp import _check_mcp_servers
from agent.doctor.model_provider_http import (
    ModelsProbeResult,
    _classify_http_result,
    _probe_model_for,
    _probe_qwen_api_key,
    _reply_from_openai_chat,
    probe_anthropic_messages,
    probe_bedrock_iam,
    probe_chat_completions,
    probe_chatgpt_plan,
    probe_llm_api_key,
    probe_models_endpoint,
    resolve_llm_probe_target,
)
from agent.mcp_catalog import McpCatalogEntry


class _JsonResp:
    def __init__(self, status_code, payload, *, bad_json=False, text=None):
        self.status_code = status_code
        self._payload = payload
        self._bad_json = bad_json
        if text is not None:
            self.text = text
        elif payload is None:
            self.text = ""
        else:
            import json

            self.text = json.dumps(payload)

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._payload


def _raise_timeout(*_args, **_kwargs):
    raise TimeoutError("timed out")


def _hide_httpx(monkeypatch):
    monkeypatch.setitem(sys.modules, "httpx", None)


def _install_httpx(monkeypatch, *, post=None, get=None):
    monkeypatch.setitem(
        sys.modules,
        "httpx",
        SimpleNamespace(post=post or _raise_timeout, get=get or _raise_timeout),
    )


def _qwen_config(monkeypatch, url):
    class _Cfg:
        def get(self, key):
            if key == "llm.qwen_base_url":
                return url
            return ""

    def load():
        return _Cfg()

    monkeypatch.setattr("agent.config.Config.load", load)


def _qwen_bases(monkeypatch, bases):
    def candidates(_api_key=None):
        return list(bases)

    monkeypatch.setattr("agent.config.qwen_base_url_candidates", candidates)


def _entry(entry_id, **overrides):
    fields = {
        "id": entry_id,
        "name": entry_id,
        "description": "coverage",
        "url": f"https://mcp.example/{entry_id}",
        "transport": "streamable_http",
    }
    fields.update(overrides)
    return McpCatalogEntry(**fields)


def _wire_mcp(monkeypatch, catalog, servers=(), *, store_factory=None, **overrides):
    state = {"http": [], "stdio": [], "saved": [], "cleared": [], "messages": []}
    monkeypatch.setattr("agent.mcp_catalog.MCP_CATALOG", catalog)

    if store_factory is None:

        def store_factory():
            class _Store:
                def list_mcp_servers(self, enabled_only=True):
                    assert enabled_only is True
                    return list(servers)

            return _Store()

    def credentials_configured(_entry_obj, _cfg):
        return True

    def resolve_auth_headers(_entry_obj, _cfg):
        return {"Authorization": "Bearer token"}

    def probe_mcp_server(url, headers, timeout):
        state["http"].append((url, headers, timeout))
        return {"ok": True, "toolCount": 1, "message": "ok"}

    def probe_stdio_mcp_server(command, args, timeout):
        state["stdio"].append((command, list(args), timeout))
        return {"ok": True, "toolCount": 2, "message": "stdio ok"}

    def resolve_catalog_command(entry):
        return f"/bin/{entry.id}"

    def save_tool_count(catalog_id, tool_count):
        state["saved"].append((catalog_id, tool_count))

    def clear_tool_count(catalog_id):
        state["cleared"].append(catalog_id)

    def save_status_message(catalog_id, message):
        state["messages"].append((catalog_id, message))

    def cfg_secret(_cfg, _config_key, _env_var):
        return "secret"

    def pymol_doctor_checks():
        return [
            {
                "name": "pymol_listen",
                "status": "warn",
                "detail": "not listening",
                "fix": "Start PyMOL",
            },
            {"name": "pymol_plugin", "status": "ok", "detail": "plugin ok"},
        ]

    impl = {
        "credentials_configured": credentials_configured,
        "resolve_auth_headers": resolve_auth_headers,
        "probe_mcp_server": probe_mcp_server,
        "probe_stdio_mcp_server": probe_stdio_mcp_server,
        "resolve_catalog_command": resolve_catalog_command,
        "save_tool_count": save_tool_count,
        "clear_tool_count": clear_tool_count,
        "save_status_message": save_status_message,
        "_cfg_secret": cfg_secret,
        "pymol_doctor_checks": pymol_doctor_checks,
    }
    impl.update(overrides)
    monkeypatch.setattr("agent_server.store.AgentStore", store_factory)
    monkeypatch.setattr(
        "agent_server.mcp_service.credentials_configured", impl["credentials_configured"]
    )
    monkeypatch.setattr(
        "agent_server.mcp_service.resolve_auth_headers", impl["resolve_auth_headers"]
    )
    monkeypatch.setattr("agent_server.mcp_service.probe_mcp_server", impl["probe_mcp_server"])
    monkeypatch.setattr(
        "agent_server.mcp_service.probe_stdio_mcp_server", impl["probe_stdio_mcp_server"]
    )
    monkeypatch.setattr("agent.mcp_catalog.resolve_catalog_command", impl["resolve_catalog_command"])
    monkeypatch.setattr("agent_server.mcp_service.save_tool_count", impl["save_tool_count"])
    monkeypatch.setattr("agent_server.mcp_service.clear_tool_count", impl["clear_tool_count"])
    monkeypatch.setattr(
        "agent_server.mcp_service.save_status_message", impl["save_status_message"]
    )
    monkeypatch.setattr("agent_server.mcp_service._cfg_secret", impl["_cfg_secret"])
    monkeypatch.setattr("agent.mcps.pymol_mcp.pymol_doctor_checks", impl["pymol_doctor_checks"])
    return state


def test_probe_chat_completions_failure_modes(monkeypatch):
    _hide_httpx(monkeypatch)
    missing = probe_chat_completions(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": "Bearer sk"},
        label="OpenAI",
        model="gpt-4o-mini",
    )
    assert missing.ok is False
    assert "httpx is not installed" in missing.message

    _install_httpx(monkeypatch, post=_raise_timeout)
    offline = probe_chat_completions(
        "https://api.openai.com/v1/chat/completions",
        {},
        label="OpenAI",
        model="gpt-4o-mini",
    )
    assert offline.ok is False
    assert "TimeoutError" in offline.message

    def post(*_args, **_kwargs):
        return _JsonResp(200, None, bad_json=True, text="not-json")

    _install_httpx(monkeypatch, post=post)
    parsed = probe_chat_completions(
        "https://api.openai.com/v1/chat/completions",
        {},
        label="OpenAI",
        model="gpt-4o-mini",
    )
    assert parsed.ok is True
    assert parsed.message == "OpenAI API key works."


def test_probe_anthropic_messages_paths(monkeypatch):
    seen = {}

    def post(*args, **kwargs):
        seen["url"] = args[0]
        seen["headers"] = kwargs["headers"]
        seen["json"] = kwargs["json"]
        return _JsonResp(
            200,
            {"content": [{"type": "text", "text": "pong"}, {"type": "tool"}]},
        )

    _install_httpx(monkeypatch, post=post)
    ok = probe_anthropic_messages("sk-ant-test")
    assert ok.ok is True
    assert "pong" in ok.message
    assert seen["url"] == "https://api.anthropic.com/v1/messages"
    assert seen["headers"]["x-api-key"] == "sk-ant-test"
    assert seen["json"]["max_tokens"] == 1
    assert "haiku" in seen["json"]["model"]

    _hide_httpx(monkeypatch)
    missing = probe_anthropic_messages("sk-ant-test", label="Anthropic")
    assert "httpx is not installed" in missing.message

    _install_httpx(monkeypatch, post=_raise_timeout)
    offline = probe_anthropic_messages("sk-ant-test", label="Anthropic")
    assert "Couldn't reach Anthropic (TimeoutError)" in offline.message

    def bad_post(*_args, **_kwargs):
        return _JsonResp(401, None, bad_json=True, text="unauthorized")

    _install_httpx(monkeypatch, post=bad_post)
    invalid = probe_anthropic_messages("sk-ant-test", label="Anthropic")
    assert invalid.ok is False
    assert invalid.message.startswith("Invalid API key.")


def test_probe_bedrock_iam_paths(monkeypatch):
    state = {"mode": "ok"}

    class _Client:
        def list_foundation_models(self, byOutputModality="TEXT"):
            assert byOutputModality == "TEXT"
            mode = state["mode"]
            if mode == "ok":
                return {"modelSummaries": [{}, {}, {}]}
            if mode == "empty":
                return {}
            if mode == "creds":
                raise RuntimeError("Unable to locate credentials")
            if mode == "denied":
                raise RuntimeError("not authorized to list models")
            raise RuntimeError("throttled")

    def client(service, _cfg):
        assert service == "bedrock"
        return _Client()

    def region(_cfg):
        return "eu-west-1"

    def load():
        return SimpleNamespace()

    monkeypatch.setattr("agent.config.bedrock_auth.bedrock_boto3_client", client)
    monkeypatch.setattr("agent.config.bedrock_auth.bedrock_region", region)
    monkeypatch.setattr("agent.config.Config.load", load)

    ok = probe_llm_api_key("bedrock", "", label="Bedrock IAM")
    assert ok.ok is True
    assert ok.model_count == 3
    assert "eu-west-1" in ok.message
    assert "Bedrock IAM" in ok.message

    state["mode"] = "empty"
    empty = probe_bedrock_iam()
    assert empty.ok is True
    assert empty.model_count == 0
    assert "Amazon Bedrock" in empty.message

    state["mode"] = "creds"
    creds = probe_bedrock_iam(label="Bedrock")
    assert creds.ok is False
    assert "aws configure" in creds.message

    state["mode"] = "denied"
    denied = probe_bedrock_iam(label="Bedrock")
    assert "Access denied" in denied.message
    assert "ListFoundationModels" in denied.message

    state["mode"] = "other"
    other = probe_bedrock_iam(label="Bedrock")
    assert other.message == "Bedrock probe failed (RuntimeError)."


def test_probe_chatgpt_plan_paths(monkeypatch):
    def auth_fail():
        raise ChatGPTAuthError("signed out")

    monkeypatch.setattr("agent.config.chatgpt_auth.access_token", auth_fail)
    signed_out = probe_chatgpt_plan()
    assert signed_out.ok is False
    assert signed_out.message == "signed out"

    def token():
        return "tok-test"

    monkeypatch.setattr("agent.config.chatgpt_auth.access_token", token)
    _hide_httpx(monkeypatch)
    missing = probe_chatgpt_plan()
    assert "cannot test the sign-in" in missing.message

    _install_httpx(monkeypatch, post=_raise_timeout)
    offline = probe_chatgpt_plan()
    assert offline.message == "Couldn't reach OpenAI (TimeoutError)."

    def limited(*_args, **_kwargs):
        return _JsonResp(429, None, bad_json=True, text="")

    _install_httpx(monkeypatch, post=limited)
    rate = probe_chatgpt_plan(label="Plus")
    assert rate.ok is False
    assert rate.status_code == 429
    assert "Plus limit reached" in rate.message

    seen = {}

    def post(*_args, **kwargs):
        seen["timeout"] = kwargs["timeout"]
        seen["headers"] = kwargs["headers"]
        seen["json"] = kwargs["json"]
        return _JsonResp(200, {"output": "pong"})

    _install_httpx(monkeypatch, post=post)
    ok = probe_llm_api_key("openai-chatgpt", "", timeout=5)
    assert ok.ok is True
    assert ok.message == "ChatGPT plan is connected and working."
    assert seen["timeout"] == 30.0
    assert seen["headers"]["Authorization"] == "Bearer tok-test"
    assert seen["json"]["model"] == "gpt-5.6-sol"
    assert seen["json"]["store"] is False

    def invalid(*_args, **_kwargs):
        return _JsonResp(401, {"error": {"message": "bad token"}}, text="unauthorized")

    _install_httpx(monkeypatch, post=invalid)
    rejected = probe_chatgpt_plan(label="ChatGPT plan", timeout=45)
    assert rejected.ok is False
    assert "Invalid API key" in rejected.message


def test_probe_model_for_fallbacks_and_provider_routing(monkeypatch):
    monkeypatch.setitem(
        OPENAI_COMPATIBLE_PROVIDERS,
        "coverage-probe",
        {
            "default_model": "widget-mini",
            "base_url": "https://example.test/v1",
            "label": "Widget",
        },
    )
    monkeypatch.setitem(
        OPENAI_COMPATIBLE_PROVIDERS,
        "coverage-empty",
        {"default_model": "   ", "base_url": "https://example.test/v1", "label": "Empty"},
    )
    assert _probe_model_for("coverage-probe") == "widget-mini"
    assert _probe_model_for("coverage-empty") == "gpt-5-nano"
    assert _probe_model_for("no-such-provider") == "gpt-5-nano"

    seen = {}

    def fake(url, headers, *, label, model, timeout=30.0):
        seen["url"] = url
        seen["headers"] = dict(headers)
        seen["label"] = label
        seen["model"] = model
        seen["timeout"] = timeout
        return ModelsProbeResult(ok=True, message=f"{label} API key works.", status_code=200)

    monkeypatch.setattr("agent.doctor.model_provider_http.probe_chat_completions", fake)

    openai = probe_llm_api_key("openai", " sk-live ", label="OpenAI", timeout=45)
    assert openai.ok is True
    assert seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer sk-live"
    assert seen["model"] == "gpt-5-nano"
    assert seen["timeout"] == 45

    empty = probe_llm_api_key("openai", "   ", label="OpenAI")
    assert empty.ok is False
    assert "Enter a OpenAI API key" in empty.message

    unsupported = probe_llm_api_key("slack", "xoxb", label=None)
    assert unsupported.message == "Live key test is not supported for slack."

    widget = probe_llm_api_key("coverage-probe", "wk", timeout=5)
    assert widget.ok is True
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["model"] == "widget-mini"
    assert seen["label"] == "Widget"
    assert seen["timeout"] == 30.0

    routed = probe_llm_api_key("openrouter", "sk-or", label=None, timeout=5)
    assert routed.ok is True
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["model"] == "openai/gpt-4o-mini"
    assert seen["label"] == "OpenRouter"
    assert seen["headers"]["Authorization"] == "Bearer sk-or"
    assert seen["headers"]["HTTP-Referer"] == "https://sandwalk.sh"
    assert seen["headers"]["X-OpenRouter-Title"] == "Sandwalk"


def test_probe_qwen_api_key_branches(monkeypatch):
    calls = []

    def fake(url, headers, *, label, model, timeout=30.0):
        calls.append((url, model, headers["Authorization"], label, timeout))
        if "blank-skip" in url and model == "qwen3.7-plus":
            return ModelsProbeResult(ok=False, message="model not found", status_code=404)
        if "blank-skip" in url:
            return ModelsProbeResult(ok=True, message=f"{label} API key works.", status_code=200)
        if "rate-limit" in url:
            return ModelsProbeResult(ok=False, message="rate limited", status_code=429)
        if "configured-auth" in url:
            return ModelsProbeResult(
                ok=False,
                message="Invalid API key. (expired)",
                status_code=401,
            )
        if "all-miss" in url:
            return ModelsProbeResult(
                ok=False,
                message="model not found",
                status_code=401,
            )
        if "host-a" in url or "host-b" in url:
            return ModelsProbeResult(ok=False, message="Invalid API key.", status_code=403)
        raise AssertionError(f"unexpected qwen probe {url} {model}")

    monkeypatch.setattr("agent.doctor.model_provider_http.probe_chat_completions", fake)

    _qwen_config(monkeypatch, "")
    _qwen_bases(monkeypatch, ["", ""])

    def unused(*_args, **_kwargs):
        raise AssertionError("blank hosts must not be probed")

    monkeypatch.setattr("agent.doctor.model_provider_http.probe_chat_completions", unused)
    blank = _probe_qwen_api_key("sk-q", label="Qwen", timeout=30)
    assert blank.ok is False
    assert blank.message.startswith("Couldn't validate Qwen")

    monkeypatch.setattr("agent.doctor.model_provider_http.probe_chat_completions", fake)
    calls.clear()
    _qwen_bases(monkeypatch, ["", "https://blank-skip.example/v1"])
    found = _probe_qwen_api_key("sk-q", label="Qwen", timeout=12)
    assert found.ok is True
    assert found.base_url == "https://blank-skip.example/v1"
    assert [model for _url, model, _auth, _label, _timeout in calls] == [
        "qwen3.7-plus",
        "qwen3.7-flash",
    ]
    assert calls[0][2] == "Bearer sk-q"
    assert calls[0][4] == 12

    calls.clear()
    _qwen_bases(monkeypatch, ["https://rate-limit.example/v1"])
    limited = _probe_qwen_api_key("sk-q", label="Qwen", timeout=30)
    assert limited.ok is False
    assert limited.message == "rate limited"
    assert limited.status_code == 429
    assert limited.base_url == "https://rate-limit.example/v1"
    assert len(calls) == 1

    calls.clear()
    configured = "https://configured-auth.example/compatible-mode/v1"
    _qwen_config(monkeypatch, configured)
    rejected = _probe_qwen_api_key("sk-q", label="Qwen", timeout=30)
    assert rejected.ok is False
    assert "selected endpoint" in rejected.message
    assert configured in rejected.message
    assert rejected.base_url == configured
    assert len(calls) == 1

    calls.clear()
    miss_host = "https://all-miss.example/compatible-mode/v1"
    _qwen_config(monkeypatch, miss_host)
    missed = _probe_qwen_api_key("sk-q", label="Qwen", timeout=30)
    assert missed.ok is False
    assert "no probe model" in missed.message
    assert missed.base_url == miss_host
    assert len(calls) == 6

    calls.clear()
    _qwen_config(monkeypatch, "")
    _qwen_bases(
        monkeypatch,
        ["https://host-a.example/v1", "https://host-b.example/v1"],
    )
    exhausted = _probe_qwen_api_key("sk-q", label="Qwen", timeout=30)
    assert exhausted.ok is False
    assert exhausted.status_code == 403
    assert exhausted.message.startswith("Invalid API key.")
    assert [url for url, _model, _auth, _label, _timeout in calls] == [
        "https://host-a.example/v1/chat/completions",
        "https://host-b.example/v1/chat/completions",
    ]


def test_probe_models_endpoint_shapes(monkeypatch):
    responses = []

    def get(*_args, **kwargs):
        assert kwargs["timeout"] == 10.0
        assert kwargs["follow_redirects"] is True
        return responses.pop(0)

    _install_httpx(monkeypatch, get=get)
    responses.append(_JsonResp(200, {"models": [{"id": "a"}, {"id": "b"}]}))
    plural = probe_models_endpoint(
        "https://example.test/v1/models",
        {"Authorization": "Bearer x"},
        label="Example",
    )
    assert plural.ok is True
    assert plural.model_count == 2
    assert "2 models" in plural.message

    responses.append(_JsonResp(200, {"data": {"id": "not-a-list"}}))
    empty = probe_models_endpoint("https://example.test/v1/models", {}, label="Example")
    assert empty.ok is True
    assert empty.model_count == 0
    assert empty.message == "Example API key works."

    responses.append(_JsonResp(200, ["not-a-dict"]))
    listed = probe_models_endpoint("https://example.test/v1/models", {}, label="Example")
    assert listed.ok is True
    assert listed.model_count == 0

    responses.append(_JsonResp(200, None, bad_json=True, text="plain"))
    bad_json = probe_models_endpoint("https://example.test/v1/models", {}, label="Example")
    assert bad_json.ok is True
    assert bad_json.model_count == 0

    responses.append(_JsonResp(503, {"message": "down"}))
    failed = probe_models_endpoint("https://example.test/v1/models", {}, label="Example")
    assert failed.ok is False
    assert "HTTP 503" in failed.message
    assert failed.model_count == 0

    def get_boom(*_args, **_kwargs):
        raise ConnectionError("refused")

    _install_httpx(monkeypatch, get=get_boom)
    offline = probe_models_endpoint("https://example.test/v1/models", {}, label="Example")
    assert "ConnectionError" in offline.message

    _hide_httpx(monkeypatch)
    missing = probe_models_endpoint("https://example.test/v1/models", {}, label="Example")
    assert "httpx is not installed" in missing.message


def test_resolve_llm_probe_target_is_retired():
    assert resolve_llm_probe_target("openai", "sk-test") is None


def test_auth_marker_outside_401_and_non_dict_choice():
    marked = _classify_http_result(
        label="OpenAI",
        code=400,
        body_text="Invalid authentication credentials",
        payload={"error": {"message": "bad"}},
        success_message="works",
    )
    assert marked.ok is False
    assert marked.message == "Invalid API key. (bad)"
    bare = _classify_http_result(
        label="OpenAI",
        code=422,
        body_text="authorization failed",
        payload=None,
        success_message="works",
    )
    assert bare.message == "Invalid API key."
    assert _reply_from_openai_chat({"choices": ["not-a-dict"]}) == ""


def test_mcp_catalog_import_failure(monkeypatch):
    monkeypatch.delattr("agent.mcp_catalog.MCP_CATALOG")
    checks = _check_mcp_servers(SimpleNamespace())
    assert len(checks) == 1
    assert checks[0].name == "mcp_catalog"
    assert checks[0].status == "warn"
    assert "MCP catalog unavailable" in checks[0].detail


def test_mcp_store_load_failure(monkeypatch):
    class _Store:
        def list_mcp_servers(self, enabled_only=True):
            assert enabled_only is True
            raise RuntimeError("db locked")

    def factory():
        return _Store()

    monkeypatch.setattr("agent_server.store.AgentStore", factory)
    checks = _check_mcp_servers(SimpleNamespace())
    assert len(checks) == 1
    assert checks[0].name == "mcp_store"
    assert checks[0].status == "warn"
    assert "db locked" in checks[0].detail
    assert checks[0].fix == "Restart `sandwalk serve`"


def test_mcp_catalog_branches(monkeypatch):
    catalog = [
        _entry("pymol", name="PyMOL", transport="stdio", url=None),
        _entry("stdio-missing", name="Missing", transport="stdio", url=None),
        _entry("stdio-ok", name="Stdio Ok", transport="stdio", url=None, args=None),
        _entry("stdio-save-boom", name="Stdio Save", transport="stdio", url=None),
        _entry("stdio-down", name="Stdio Down", transport="stdio", url=None),
        _entry("stdio-down-boom", name="Stdio Down Boom", transport="stdio", url=None),
        _entry("disabled-creds", name="Disabled Creds"),
        _entry("disabled-skip", name="Disabled Skip"),
        _entry("remote-noauth", name="No Auth"),
        _entry("remote-ok", name="Remote Ok"),
        _entry("remote-ok-boom", name="Remote Save"),
        _entry("remote-down", name="Remote Down"),
        _entry("remote-down-boom", name="Remote Down Boom"),
        _entry("remote-nourl", name="No URL", url=None),
    ]
    servers = [
        SimpleNamespace(id="s-stdio-missing", name="Missing", catalog_id="stdio-missing", url=None),
        SimpleNamespace(id="s-stdio-ok", name="Stdio Ok", catalog_id="stdio-ok", url=None),
        SimpleNamespace(
            id="s-stdio-save-boom", name="Stdio Save", catalog_id="stdio-save-boom", url=None
        ),
        SimpleNamespace(id="s-stdio-down", name="Stdio Down", catalog_id="stdio-down", url=None),
        SimpleNamespace(
            id="s-stdio-down-boom",
            name="Stdio Down Boom",
            catalog_id="stdio-down-boom",
            url=None,
        ),
        SimpleNamespace(id="s-noauth", name="No Auth", catalog_id="remote-noauth", url="https://x"),
        SimpleNamespace(id="s-ok", name="Remote Ok", catalog_id="remote-ok", url="https://x"),
        SimpleNamespace(
            id="s-ok-boom", name="Remote Save", catalog_id="remote-ok-boom", url="https://x"
        ),
        SimpleNamespace(id="s-down", name="Remote Down", catalog_id="remote-down", url="https://x"),
        SimpleNamespace(
            id="s-down-boom",
            name="Remote Down Boom",
            catalog_id="remote-down-boom",
            url="https://x",
        ),
        SimpleNamespace(id="s-nourl", name="No URL", catalog_id="remote-nourl", url=None),
    ]
    customs = [
        SimpleNamespace(id="okcust01aaaaaaaa", name="Custom Ok", url="https://custom.example/ok"),
        SimpleNamespace(id="bad00002bbbbbbbb", name="Custom Bad", url="https://custom.example/bad"),
        SimpleNamespace(id="c3cust03cccccccc", name="C3", url="https://custom.example/c3"),
        SimpleNamespace(id="c4cust04dddddddd", name="C4", url="https://custom.example/c4"),
        SimpleNamespace(id="c5cust05eeeeeeee", name="C5", url="https://custom.example/c5ok"),
        SimpleNamespace(id="c6cust06ffffffff", name="C6", url="https://custom.example/c6"),
        SimpleNamespace(id="blankurl99999999", name="Blank", url=""),
    ]

    def credentials_configured(entry, _cfg):
        return entry.id not in {"stdio-missing", "disabled-skip"}

    def resolve_auth_headers(entry, _cfg):
        if entry.id == "remote-noauth":
            return {}
        return {"Authorization": "Bearer token"}

    def resolve_catalog_command(entry):
        if entry.id == "stdio-ok":
            return None
        return f"/bin/{entry.id}"

    def probe_stdio_mcp_server(command, args, timeout):
        state["stdio"].append((command, list(args), timeout))
        if command == "":
            return {"ok": True, "toolCount": 3, "message": "up"}
        if command.endswith("stdio-save-boom"):
            return {"ok": True, "toolCount": 0, "message": "up"}
        if command.endswith("stdio-down"):
            return {"ok": False, "message": "", "toolCount": 0}
        return {"ok": False, "message": "closed", "toolCount": 0}

    def probe_mcp_server(url, headers, timeout):
        state["http"].append((url, headers, timeout))
        if url == "":
            return {"ok": True, "toolCount": 1, "message": "nourl"}
        if url.endswith("/remote-ok"):
            return {"ok": True, "toolCount": 4, "message": "ready"}
        if url.endswith("/remote-ok-boom"):
            return {"ok": True, "toolCount": 0, "message": "ready"}
        if url.endswith("/remote-down"):
            return {"ok": False, "message": "timeout", "toolCount": 0}
        if url.endswith("/remote-down-boom"):
            return {"ok": False, "message": "closed", "toolCount": 0}
        if url.startswith("https://custom.example"):
            ok = url.endswith("ok") or url.endswith("c5ok")
            return {
                "ok": ok,
                "message": "custom up" if ok else "custom down",
                "toolCount": 2,
            }
        return {"ok": False, "message": "unmapped", "toolCount": 0}

    def save_tool_count(catalog_id, tool_count):
        state["saved"].append((catalog_id, tool_count))
        if catalog_id in {"stdio-save-boom", "remote-ok-boom"}:
            raise OSError("save failed")

    def clear_tool_count(catalog_id):
        state["cleared"].append(catalog_id)
        if catalog_id == "stdio-down-boom":
            raise OSError("clear failed")

    def save_status_message(catalog_id, message):
        state["messages"].append((catalog_id, message))
        if catalog_id == "remote-down-boom":
            raise OSError("status failed")

    state = _wire_mcp(
        monkeypatch,
        catalog,
        [*servers, *customs],
        credentials_configured=credentials_configured,
        resolve_auth_headers=resolve_auth_headers,
        resolve_catalog_command=resolve_catalog_command,
        probe_stdio_mcp_server=probe_stdio_mcp_server,
        probe_mcp_server=probe_mcp_server,
        save_tool_count=save_tool_count,
        clear_tool_count=clear_tool_count,
        save_status_message=save_status_message,
    )
    checks = {row.name: row for row in _check_mcp_servers(SimpleNamespace())}

    assert checks["pymol_listen"].status == "warn"
    assert checks["pymol_listen"].fix == "Start PyMOL"
    assert checks["pymol_plugin"].status == "ok"
    assert checks["pymol_plugin"].fix is None
    assert "mcp_pymol" not in checks

    assert checks["mcp_stdio-missing"].status == "error"
    assert "launcher is missing" in checks["mcp_stdio-missing"].detail
    assert checks["mcp_stdio-ok"].detail == "Stdio Ok: 3 tools"
    assert ("stdio-ok", 3) in state["saved"]
    assert ("", [], 25.0) in state["stdio"]
    assert checks["mcp_stdio-save-boom"].status == "ok"
    assert "0 tools" in checks["mcp_stdio-save-boom"].detail
    assert checks["mcp_stdio-down"].status == "error"
    assert checks["mcp_stdio-down"].detail == "Stdio Down: "
    assert ("stdio-down", "Connection failed") in state["messages"]
    assert checks["mcp_stdio-down-boom"].status == "error"
    assert "stdio-down-boom" in state["cleared"]
    assert "stdio-down-boom" not in {catalog_id for catalog_id, _msg in state["messages"]}

    assert checks["mcp_disabled-creds"].status == "warn"
    assert "disabled" in checks["mcp_disabled-creds"].detail
    assert "mcp_disabled-skip" not in checks

    assert checks["mcp_remote-noauth"].status == "error"
    assert "not authenticated" in checks["mcp_remote-noauth"].detail
    assert checks["mcp_remote-ok"].detail == "Remote Ok: 4 tools"
    assert checks["mcp_remote-ok-boom"].status == "ok"
    assert ("remote-ok-boom", 0) in state["saved"]
    assert checks["mcp_remote-down"].detail == "Remote Down: timeout"
    assert ("remote-down", "timeout") in state["messages"]
    assert checks["mcp_remote-down"].fix.startswith("Reconnect")
    assert checks["mcp_remote-down-boom"].status == "error"
    assert ("remote-down-boom", "closed") in state["messages"]
    assert checks["mcp_remote-nourl"].status == "ok"
    assert ("", {"Authorization": "Bearer token"}, 25.0) in state["http"]

    custom_names = [name for name in checks if name.startswith("mcp_custom_")]
    assert custom_names == [
        "mcp_custom_okcust01",
        "mcp_custom_bad00002",
        "mcp_custom_c3cust03",
        "mcp_custom_c4cust04",
        "mcp_custom_c5cust05",
    ]
    assert checks["mcp_custom_okcust01"].status == "ok"
    assert checks["mcp_custom_bad00002"].status == "warn"
    assert "custom down" in checks["mcp_custom_bad00002"].detail
    assert all(timeout == 15.0 for url, _headers, timeout in state["http"] if "custom" in url)


def test_mcp_enabled_pymol_falls_through_to_stdio(monkeypatch):
    catalog = [_entry("pymol", name="PyMOL", transport="stdio", url=None)]
    servers = [SimpleNamespace(id="pymol-1", name="PyMOL", catalog_id="pymol", url=None)]
    state = _wire_mcp(monkeypatch, catalog, servers)
    checks = {row.name: row for row in _check_mcp_servers(SimpleNamespace())}
    assert checks["pymol_listen"].category == "mcp"
    assert checks["mcp_pymol"].status == "ok"
    assert checks["mcp_pymol"].detail == "PyMOL: 2 tools"
    assert state["stdio"][0][0] == "/bin/pymol"
    assert ("pymol", 2) in state["saved"]


def test_neurosnap_retries_alternate_api_key_header(monkeypatch):
    calls = []

    def resolve_auth_headers(_entry_obj, _cfg):
        return {"Authorization": "Bearer secret"}

    def probe_mcp_server(url, headers, timeout):
        calls.append((url, dict(headers), timeout))
        if headers == {"X-API-KEY": "secret"}:
            return {"ok": True, "toolCount": 5, "message": "alt"}
        return {"ok": False, "message": "primary", "toolCount": 0}

    catalog = [
        _entry(
            "neurosnap",
            name="Neurosnap",
            url="https://neurosnap.ai/mcp",
            api_key_config_key="mcp.neurosnap_api_key",
            api_key_env_var="NEUROSNAP_API_KEY",
        )
    ]
    servers = [
        SimpleNamespace(
            id="ns",
            name="Neurosnap",
            catalog_id="neurosnap",
            url="https://neurosnap.ai/mcp",
        )
    ]
    state = _wire_mcp(
        monkeypatch,
        catalog,
        servers,
        resolve_auth_headers=resolve_auth_headers,
        probe_mcp_server=probe_mcp_server,
    )
    checks = _check_mcp_servers(SimpleNamespace())
    assert checks[-1].name == "mcp_neurosnap"
    assert checks[-1].status == "ok"
    assert checks[-1].detail == "Neurosnap: 5 tools"
    assert calls[1][1] == {"X-API-KEY": "secret"}
    assert ("neurosnap", 5) in state["saved"]


def test_neurosnap_skips_retry_without_api_key(monkeypatch):
    calls = []

    def probe_mcp_server(url, headers, timeout):
        calls.append(headers)
        return {"ok": False, "message": "denied", "toolCount": 0}

    def cfg_secret(_cfg, _config_key, _env_var):
        return None

    catalog = [_entry("neurosnap", name="Neurosnap", api_key_config_key="mcp.neurosnap_api_key")]
    servers = [SimpleNamespace(id="ns", name="Neurosnap", catalog_id="neurosnap", url="u")]
    state = _wire_mcp(
        monkeypatch,
        catalog,
        servers,
        probe_mcp_server=probe_mcp_server,
        _cfg_secret=cfg_secret,
    )
    checks = _check_mcp_servers(SimpleNamespace())
    assert len(calls) == 1
    assert checks[-1].status == "error"
    assert checks[-1].detail == "Neurosnap: denied"
    assert state["cleared"] == ["neurosnap"]
    assert state["messages"] == [("neurosnap", "denied")]


def test_neurosnap_skips_header_that_matches_primary(monkeypatch):
    calls = []

    def resolve_auth_headers(_entry_obj, _cfg):
        return {"X-API-KEY": "secret"}

    def probe_mcp_server(url, headers, timeout):
        calls.append(dict(headers))
        if "Authorization" in headers:
            return {"ok": True, "toolCount": 8, "message": "bearer"}
        return {"ok": False, "message": "xapi failed", "toolCount": 0}

    catalog = [_entry("neurosnap", name="Neurosnap")]
    servers = [SimpleNamespace(id="ns", name="Neurosnap", catalog_id="neurosnap", url="u")]
    _wire_mcp(
        monkeypatch,
        catalog,
        servers,
        resolve_auth_headers=resolve_auth_headers,
        probe_mcp_server=probe_mcp_server,
    )
    checks = _check_mcp_servers(SimpleNamespace())
    assert calls == [
        {"X-API-KEY": "secret"},
        {"Authorization": "Bearer secret"},
    ]
    assert checks[-1].status == "ok"
    assert "8 tools" in checks[-1].detail


def test_neurosnap_keeps_failure_when_alternates_fail(monkeypatch):
    calls = []

    def probe_mcp_server(url, headers, timeout):
        calls.append(dict(headers))
        return {"ok": False, "message": "still down", "toolCount": 0}

    def resolve_auth_headers(_entry_obj, _cfg):
        return {"X-Other": "nope"}

    catalog = [_entry("neurosnap", name="Neurosnap")]
    servers = [SimpleNamespace(id="ns", name="Neurosnap", catalog_id="neurosnap", url="u")]
    _wire_mcp(
        monkeypatch,
        catalog,
        servers,
        resolve_auth_headers=resolve_auth_headers,
        probe_mcp_server=probe_mcp_server,
    )
    checks = _check_mcp_servers(SimpleNamespace())
    assert calls == [
        {"X-Other": "nope"},
        {"X-API-KEY": "secret"},
        {"Authorization": "Bearer secret"},
    ]
    assert checks[-1].status == "error"
    assert checks[-1].detail == "Neurosnap: still down"


def test_custom_mcp_list_failure_keeps_catalog_checks(monkeypatch):
    class _Store:
        def __init__(self):
            self.calls = 0

        def list_mcp_servers(self, enabled_only=True):
            self.calls += 1
            if self.calls > 1:
                raise RuntimeError("custom query failed")
            return [
                SimpleNamespace(
                    id="srv",
                    name="Remote Ok",
                    catalog_id="remote-ok",
                    url="https://mcp.example/remote-ok",
                )
            ]

    def factory():
        return _Store()

    catalog = [_entry("remote-ok", name="Remote Ok")]
    _wire_mcp(monkeypatch, catalog, store_factory=factory)
    checks = _check_mcp_servers(SimpleNamespace())
    assert [row.name for row in checks] == ["mcp_remote-ok"]
    assert checks[0].status == "ok"
