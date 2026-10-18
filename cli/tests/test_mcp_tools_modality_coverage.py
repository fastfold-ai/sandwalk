"""Coverage for MCP tool loading edges and modality sanitizing.

No live MCP servers: clients, stdio adapters, and loaders are fakes.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import time
from unittest.mock import patch

# Keep RootModel registered before MCP imports. Under coverage, pydantic can
# drop this module mid-import and JSONRPCMessage then raises KeyError.
import pydantic.root_model  # noqa: F401
import pytest

from agent.deepagents_runtime import mcp_tools
from agent.deepagents_runtime import modality_sanitize as modality

PNG_B64 = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode("ascii")


class _Tool:
    def __init__(self, name):
        self.name = name


class _Request:
    def __init__(self, messages):
        self.messages = messages

    def override(self, **overrides):
        updated = _Request(overrides.get("messages", self.messages))
        updated.overrides = overrides
        return updated


class _PlainMessage:
    """No ``model_copy``; content can be assigned."""

    def __init__(self, content):
        self.content = content


class _LockedMessage:
    def __init__(self, content):
        self._content = content

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, value):
        raise TypeError("locked")


class _DumpOk:
    def model_dump(self):
        return {"type": "audio", "mime_type": "audio/wav"}


class _DumpBoom:
    def model_dump(self):
        raise ValueError("dump failed")


class _DumpList:
    def model_dump(self):
        return ["not", "a", "dict"]


class _NotCallableDump:
    model_dump = "nope"


class _SaveDir:
    def __init__(self, *, mkdir_error=False, write_error=False):
        self.mkdir_error = mkdir_error
        self.write_error = write_error
        self.child_name = None

    def mkdir(self, parents=False, exist_ok=False):
        if self.mkdir_error:
            raise OSError("mkdir failed")

    def __truediv__(self, other):
        self.child_name = other
        return self

    def exists(self):
        return False

    def write_bytes(self, data):
        if self.write_error:
            raise OSError("write failed")
        self.data = data

    def __str__(self):
        return f"/tmp/{self.child_name}"


class _FakeStdioClient:
    def __init__(self):
        self.errlogs = []

    def __call__(self, server, errlog=None):
        self.errlogs.append(errlog)
        self.server = server
        return self

    async def __aenter__(self):
        return ("read", "write")

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeMcpClient:
    def __init__(self, mapping):
        self.mapping = mapping

    async def get_tools(self):
        return [_Tool("from-client")]


@pytest.fixture(autouse=True)
def _clear_mcp_caches():
    mcp_tools.clear_mcp_tool_caches()
    yield
    mcp_tools.clear_mcp_tool_caches()


def _http_server(name: str, url: str = "https://example.com/mcp") -> dict:
    return {
        "name": name,
        "enabled": True,
        "transport": "streamable_http",
        "url": url,
    }


def _image_block() -> dict:
    return {"type": "image", "base64": PNG_B64, "mime_type": "image/png"}


def _fail_background_refresh(coro, *_args, **_kwargs):
    close = getattr(coro, "close", None)
    if close is not None:
        close()
    raise RuntimeError("background refresh failed")


async def _load_raises(name, connection):
    raise ConnectionError(f"down:{name}")


async def _should_not_load(name, connection):
    raise AssertionError(f"unexpected load of {name}")


def test_connection_for_server_rejects_unusable_and_builds_http():
    disabled = {
        "enabled": False,
        "name": "off",
        "transport": "sse",
        "url": "https://example.com/mcp",
    }
    assert mcp_tools._connection_for_server(disabled) is None
    assert (
        mcp_tools._connection_for_server(
            {"name": "x", "transport": "websocket", "url": "https://example.com/mcp"}
        )
        is None
    )
    assert (
        mcp_tools._connection_for_server(
            {
                "name": "  ",
                "id": "from-id",
                "transport": "sse",
                "url": "https://example.com/mcp",
            }
        )
        is None
    )
    assert (
        mcp_tools._connection_for_server(
            {"name": "bare", "transport": "http"}
        )
        is None
    )
    assert (
        mcp_tools._connection_for_server({"name": "pymol", "transport": "stdio"})
        is None
    )

    name, connection = mcp_tools._connection_for_server(
        {
            "name": "",
            "id": "from-id",
            "type": "sse",
            "url": "https://example.com/sse",
            "headers": {"Authorization": "Bearer t", "X-Num": 7},
        }
    )
    assert name == "from-id"
    assert connection["transport"] == "sse"
    assert connection["headers"]["Authorization"] == "Bearer t"
    assert connection["headers"]["X-Num"] == "7"
    assert "User-Agent" in connection["headers"]

    name, connection = mcp_tools._connection_for_server(
        {
            "name": "custom-ua",
            "transport": "streamablehttp",
            "url": "https://example.com/mcp",
            "headers": {"user-agent": "CustomAgent"},
        }
    )
    assert connection["transport"] == "streamable_http"
    assert connection["headers"] == {"user-agent": "CustomAgent"}

    name, connection = mcp_tools._connection_for_server(
        {
            "name": "no-headers",
            "transport": "http",
            "url": "https://example.com/mcp",
            "headers": "nope",
        }
    )
    assert list(connection["headers"]) == ["User-Agent"]


def test_stdio_connection_cache_key_and_timeout():
    name, connection = mcp_tools._connection_for_server(
        {
            "name": "pymol",
            "transport": "stdio",
            "command": "python",
            "args": ["-m", "pymol"],
            "env": {"FOO": "bar", "N": 1},
        }
    )
    assert name == "pymol"
    assert connection["command"] == "python"
    assert connection["args"] == ["-m", "pymol"]
    assert connection["env"] == {"FOO": "bar", "N": "1"}
    key = mcp_tools._cache_key(name, connection)
    assert key == "stdio:pymol:python:-m pymol"
    assert mcp_tools._default_timeout(connection) == mcp_tools.DEFAULT_STDIO_TIMEOUT_S

    _name, bare = mcp_tools._connection_for_server(
        {
            "name": "echo",
            "transport": "stdio",
            "command": "echo",
            "env": {},
        }
    )
    assert "env" not in bare
    assert bare["args"] == []
    assert (
        mcp_tools._default_timeout({"transport": "sse", "url": "https://x"})
        == mcp_tools.DEFAULT_HTTP_TIMEOUT_S
    )
    assert mcp_tools._cache_key("h", {"transport": "sse", "url": "https://x"}) == (
        "sse:h:https://x"
    )


def test_stale_cache_without_allow_stale_and_expired_cooldown():
    mcp_tools._success_cache["aged"] = (
        time.monotonic() - mcp_tools.SUCCESS_CACHE_TTL_S - 5,
        [_Tool("old")],
        ["old"],
    )
    assert mcp_tools._cached_success("aged", allow_stale=False) is None
    assert "aged" in mcp_tools._success_cache

    mcp_tools._failure_until["cool"] = time.monotonic() - 0.01
    assert mcp_tools._in_failure_cooldown("cool") is False
    assert "cool" not in mcp_tools._failure_until
    assert mcp_tools._in_failure_cooldown("missing") is False


def test_background_refresh_skips_when_lock_held_and_swallows_errors():
    connection = {"transport": "sse", "url": "https://example.com/mcp"}
    key = mcp_tools._cache_key("busy", connection)
    lock = mcp_tools._inflight_lock(key)
    assert lock.acquire(blocking=False)
    try:
        with patch.object(mcp_tools.threading, "Thread") as thread_cls:
            mcp_tools._refresh_in_background("busy", connection, 1.0)
        thread_cls.assert_not_called()
    finally:
        lock.release()

    with patch.object(mcp_tools.asyncio, "run", side_effect=_fail_background_refresh):
        mcp_tools._refresh_in_background("busy", connection, 1.0)
        deadline = time.monotonic() + 2.0
        while lock.locked() and time.monotonic() < deadline:
            time.sleep(0.01)
    assert not lock.locked()


def test_index_keys_drop_blanks_and_duplicates():
    keys = mcp_tools._index_keys_for_server(
        {"catalog_id": "Cat Id", "id": "My_Server", "name": "My_Server"},
        "My_Server",
    )
    assert keys == ["Cat Id", "cat-id", "My_Server", "my-server"]
    assert mcp_tools._index_keys_for_server({}, "  ") == []


def test_quiet_stdio_errlog_is_installed_once():
    import langchain_mcp_adapters.sessions as sessions

    fake = _FakeStdioClient()
    original = sessions.stdio_client
    mcp_tools._stdio_errlog_installed = False
    mcp_tools._stdio_errlog_sink = None
    try:
        with patch("mcp.client.stdio.stdio_client", fake):
            mcp_tools.ensure_quiet_stdio_mcp_errlog()
        quiet = sessions.stdio_client
        sink = mcp_tools._stdio_errlog_sink

        async def _use():
            async with quiet("server-a") as streams:
                assert streams == ("read", "write")
            custom_err = _PlainMessage("err")
            async with quiet("server-b", errlog=custom_err) as streams:
                assert streams == ("read", "write")
            return custom_err

        custom_err = asyncio.run(_use())
        assert fake.server == "server-b"
        assert fake.errlogs[0] is sink
        assert fake.errlogs[1] is custom_err
        mcp_tools.ensure_quiet_stdio_mcp_errlog()
        assert sessions.stdio_client is quiet
    finally:
        sessions.stdio_client = original
        mcp_tools._stdio_errlog_installed = False
        sink = mcp_tools._stdio_errlog_sink
        mcp_tools._stdio_errlog_sink = None
        if sink is not None:
            sink.close()


def test_load_one_server_builds_client(monkeypatch):
    monkeypatch.setattr(
        "langchain_mcp_adapters.client.MultiServerMCPClient",
        _FakeMcpClient,
    )
    mcp_tools._stdio_errlog_installed = True
    stdio_tools = asyncio.run(
        mcp_tools._load_one_server(
            "pymol",
            {"transport": "stdio", "command": "python", "args": []},
        )
    )
    http_tools = asyncio.run(
        mcp_tools._load_one_server(
            "remote",
            {"transport": "sse", "url": "https://example.com/mcp"},
        )
    )
    assert [tool.name for tool in stdio_tools] == ["from-client"]
    assert [tool.name for tool in http_tools] == ["from-client"]


def test_create_returns_empty_for_no_servers_or_unusable_entries():
    assert asyncio.run(mcp_tools.create_external_mcp_tools(None)) == []
    assert asyncio.run(mcp_tools.create_external_mcp_tools([])) == []

    async def _run():
        with patch.object(mcp_tools, "_load_one_server", side_effect=_should_not_load):
            return await mcp_tools.create_external_mcp_tools(
                [
                    {
                        "enabled": False,
                        "name": "off",
                        "transport": "stdio",
                        "command": "python",
                    },
                    {"name": "bad", "transport": "websocket", "url": "https://x"},
                ]
            )

    assert asyncio.run(_run()) == []


def test_create_loads_stdio_dedupes_tools_and_indexes_names():
    loads: list[str] = []

    async def _load(name, connection):
        loads.append(name)
        if name == "pymol":
            return [
                _Tool("shared"),
                _Tool(""),
                _Tool("   "),
                _Tool("shared"),
                _Tool("only-stdio"),
            ]
        return [_Tool("shared"), _Tool("only-http")]

    mcp_tools._stdio_errlog_installed = True
    out: dict[str, list[str]] = {}

    async def _run():
        with patch.object(mcp_tools, "_load_one_server", side_effect=_load):
            return await mcp_tools.create_external_mcp_tools(
                [
                    {
                        "enabled": False,
                        "name": "skipped",
                        "transport": "sse",
                        "url": "https://skip.example/mcp",
                    },
                    {
                        "name": "pymol",
                        "catalog_id": "Cat Id",
                        "id": "pymol",
                        "transport": "stdio",
                        "command": "python",
                        "args": ["-m", "pymol"],
                    },
                    _http_server("remote", "https://other.example/mcp"),
                ],
                out_tools_by_server=out,
            )

    tools = asyncio.run(_run())
    assert loads == ["pymol", "remote"]
    assert [tool.name for tool in tools] == ["shared", "only-stdio", "only-http"]
    assert out["Cat Id"] == ["shared", "only-stdio"]
    assert out["cat-id"] == ["shared", "only-stdio"]
    assert out["pymol"] == ["shared", "only-stdio"]
    assert out["remote"] == ["shared", "only-http"]


def test_load_exception_marks_failure_only_when_cached(caplog):
    server = _http_server("latch")

    async def _cached():
        with (
            caplog.at_level(logging.WARNING, logger="runner"),
            patch.object(mcp_tools, "_load_one_server", side_effect=_load_raises),
        ):
            loaded = await mcp_tools.create_external_mcp_tools(
                [server], per_server_timeout_s=1.0, use_cache=True
            )
        return loaded

    assert asyncio.run(_cached()) == []
    assert "Unable to load MCP tools from latch" in caplog.text
    connection = mcp_tools._connection_for_server(server)
    assert connection is not None
    assert mcp_tools._in_failure_cooldown(mcp_tools._cache_key(*connection))

    mcp_tools.clear_mcp_tool_caches()
    caplog.clear()

    async def _uncached():
        with patch.object(mcp_tools, "_load_one_server", side_effect=_load_raises):
            return await mcp_tools.create_external_mcp_tools(
                [server], per_server_timeout_s=1.0, use_cache=False
            )

    assert asyncio.run(_uncached()) == []
    assert not mcp_tools._failure_until


def test_concurrent_wait_timeout_and_cooldown_after_acquire(caplog):
    connection = {"transport": "sse", "url": "https://example.com/mcp"}
    name = "latch"
    key = mcp_tools._cache_key(name, connection)

    async def _timeout():
        async def _deny(func, *args, **kwargs):
            return False

        with (
            caplog.at_level(logging.WARNING, logger="runner"),
            patch.object(mcp_tools.asyncio, "to_thread", _deny),
            patch.object(mcp_tools, "_load_one_server", side_effect=_should_not_load),
        ):
            return await mcp_tools._load_server_entry(
                server={"name": name},
                name=name,
                connection=connection,
                timeout_s=0.2,
                use_cache=True,
            )

    assert asyncio.run(_timeout()) == (name, [], [])
    assert "Timed out waiting for a concurrent MCP load" in caplog.text

    async def _cooldown():
        async def _acquire_then_fail(func, *args, **kwargs):
            mcp_tools._mark_failure(key)
            return func(*args)

        with patch.object(mcp_tools.asyncio, "to_thread", _acquire_then_fail):
            with patch.object(
                mcp_tools, "_load_one_server", side_effect=_should_not_load
            ):
                return await mcp_tools._load_server_entry(
                    server={"name": name},
                    name=name,
                    connection=connection,
                    timeout_s=0.2,
                    use_cache=True,
                )

    assert asyncio.run(_cooldown()) == (name, [], [])


def test_block_dict_and_detect_modality_kinds():
    assert modality._block_dict(_DumpOk()) == {
        "type": "audio",
        "mime_type": "audio/wav",
    }
    assert modality._block_dict(_DumpBoom()) is None
    assert modality._block_dict(_DumpList()) is None
    assert modality._block_dict(_NotCallableDump()) is None
    assert modality._block_dict("text") is None

    assert modality.detect_block_modality("nope") is None
    assert modality.detect_block_modality({"type": "file"}) == "file"
    assert modality.detect_block_modality({"type": "document"}) == "file"
    assert modality.detect_block_modality({"type": "audio"}) == "audio"
    assert modality.detect_block_modality({"type": "video"}) == "video"
    assert (
        modality.detect_block_modality(
            {"type": "text", "image_url": {"url": "https://example.com/a.png"}}
        )
        == "image"
    )
    assert modality.detect_block_modality({"mime_type": "image/webp"}) == "image"
    assert modality.detect_block_modality({"mime_type": "audio/mpeg"}) == "audio"
    assert modality.detect_block_modality({"mimeType": "video/mp4"}) == "video"
    assert modality.detect_block_modality({"media_type": "application/pdf"}) == "file"
    assert (
        modality.detect_block_modality({"media_type": "application/x-pdf"}) == "file"
    )
    assert modality.detect_block_modality({"mime_type": "text/plain"}) is None
    assert modality.detect_block_modality(_DumpOk()) == "audio"


def test_extract_bytes_from_base64_and_data_urls():
    payload, mime = modality._extract_bytes_and_mime(
        {"data": PNG_B64, "mimeType": "image/png"}
    )
    assert payload == b"\x89PNG\r\n\x1a\nfake"
    assert mime == "image/png"

    payload, mime = modality._extract_bytes_and_mime({"base64": PNG_B64})
    assert payload is not None
    assert mime == "application/octet-stream"

    payload, mime = modality._extract_bytes_and_mime(
        {"base64": "ab", "mime_type": "image/png"}
    )
    assert payload is None
    assert mime == "image/png"

    payload, mime = modality._extract_bytes_and_mime(
        {"base64": "  \n", "mime_type": "image/png"}
    )
    assert payload is None

    payload, mime = modality._extract_bytes_and_mime(
        {"image_url": {"url": f"data:image/jpeg;base64,{PNG_B64}"}}
    )
    assert payload == b"\x89PNG\r\n\x1a\nfake"
    assert mime == "image/jpeg"

    payload, mime = modality._extract_bytes_and_mime(
        {
            "mime_type": "image/png",
            "image_url": {"url": f"data:image/jpeg;base64,{PNG_B64}"},
        }
    )
    assert mime == "image/png"

    payload, mime = modality._extract_bytes_and_mime(
        {"image_url": f"data:image/gif;base64,{PNG_B64}"}
    )
    assert mime == "image/gif"
    assert payload is not None

    payload, mime = modality._extract_bytes_and_mime(
        {"url": f"data:audio/wav;base64,{PNG_B64}"}
    )
    assert mime == "audio/wav"

    payload, mime = modality._extract_bytes_and_mime(
        {"url": "data:image/png;base64,ab"}
    )
    assert payload is None
    assert mime == "image/png"

    payload, mime = modality._extract_bytes_and_mime(
        {
            "image_url": "https://example.com/a.png",
            "mime_type": "image/png",
        }
    )
    assert payload is None
    assert mime == "image/png"

    payload, mime = modality._extract_bytes_and_mime(
        {"image_url": {"url": ""}, "url": "https://example.com/a.png"}
    )
    assert payload is None


def test_save_media_oserror_and_missing_payload():
    data = {"base64": PNG_B64, "mime_type": "image/png"}
    missing = _SaveDir()
    assert (
        modality._save_media({"type": "image"}, kind="image", save_dir=missing) is None
    )
    mkdir_fail = _SaveDir(mkdir_error=True)
    assert modality._save_media(data, kind="image", save_dir=mkdir_fail) is None
    write_fail = _SaveDir(write_error=True)
    assert modality._save_media(data, kind="image", save_dir=write_fail) is None
    assert write_fail.child_name is not None
    assert write_fail.child_name.startswith("image-")


def test_sanitize_unchanged_lists_and_message_copies():
    text = [{"type": "text", "text": "keep"}]
    same, changed = modality.sanitize_content_blocks(
        text,
        unsupported=frozenset({"image", "file", "audio", "video"}),
    )
    assert changed is False
    assert same is text

    audio = {
        "type": "audio",
        "base64": base64.b64encode(b"wav").decode("ascii"),
        "mime_type": "audio/wav",
    }
    plain_text = _PlainMessage("hello")
    plain_audio = _PlainMessage([audio, {"type": "text", "text": "after"}])
    locked = _LockedMessage([dict(audio)])
    out, changed = modality.sanitize_messages(
        [plain_text, plain_audio, locked],
        unsupported=frozenset({"audio"}),
    )
    assert changed is True
    assert out[0] is plain_text
    assert out[1] is plain_audio
    assert out[1].content[0]["type"] == "text"
    assert "cannot accept audio" in out[1].content[0]["text"]
    assert out[1].content[1]["text"] == "after"
    assert out[2] is locked
    assert locked.content[0]["type"] == "audio"

    assert modality.sanitize_messages([], unsupported=frozenset({"image"})) == (
        [],
        False,
    )


def test_middleware_filters_requests_and_wraps_calls(tmp_path, caplog):
    rooted = modality.UnsupportedModalityMiddleware(
        provider="deepseek",
        model_id="deepseek-v4-flash",
        workspace_path=str(tmp_path / "proj"),
        profile={"image_inputs": False},
    )
    assert rooted._save_dir == (
        (tmp_path / "proj").resolve() / "artifacts" / "tool-images"
    )
    assert "image" in rooted._unsupported

    blank = modality.UnsupportedModalityMiddleware(
        provider=None,
        model_id=None,
        workspace_path="   ",
    )
    assert blank._save_dir is None
    assert blank._provider == ""
    assert blank._model_id == ""
    assert blank._unsupported == frozenset({"image", "file", "audio", "video"})

    open_mw = modality.UnsupportedModalityMiddleware(
        provider="deepseek",
        model_id="deepseek-v4-flash",
        profile={
            "image_inputs": True,
            "pdf_inputs": True,
            "audio_inputs": True,
            "video_inputs": True,
        },
    )
    passthrough = _Request([_PlainMessage("hi")])
    assert open_mw._unsupported == frozenset()
    assert open_mw._filter_request(passthrough) is passthrough

    unchanged = _Request(None)
    assert rooted._filter_request(unchanged) is unchanged

    from langchain_core.messages import HumanMessage

    request = _Request(
        [
            HumanMessage(
                content=[_image_block(), {"type": "text", "text": "look"}]
            )
        ]
    )
    with caplog.at_level(logging.INFO, logger="deepagents_runtime.modality"):
        updated = rooted._filter_request(request)
    assert updated is not request
    assert "Stripped unsupported multimodal blocks" in caplog.text
    assert "deepseek/deepseek-v4-flash" in caplog.text
    saved = list((tmp_path / "proj" / "artifacts" / "tool-images").glob("image-*.png"))
    assert len(saved) == 1
    assert "Saved to" in updated.messages[0].content[0]["text"]

    seen: dict[str, object] = {}

    def _handler(req):
        seen["sync"] = req
        return "sync-ok"

    async def _ahandler(req):
        seen["async"] = req
        return "async-ok"

    assert rooted.wrap_model_call(request, _handler) == "sync-ok"
    assert seen["sync"] is not request
    assert asyncio.run(rooted.awrap_model_call(request, _ahandler)) == "async-ok"
    assert seen["async"] is not request
