"""
Deep-agent (LangGraph) runtime backend for the Fastfold Agent CLI.

This is the model-agnostic alternative to the Claude Agent SDK path in
``runner.py``. It builds a :func:`deepagents.create_deep_agent` graph that:

- exposes the same 192 domain tools (wrapped as LangChain ``StructuredTool``
  objects around the existing ``mcp_server`` handlers),
- keeps the persistent ``run_python`` / ``run_r`` sandbox tools,
- loads installed skills natively via deepagents progressive disclosure
  (``skills=[...]``) so the system prompt stays compact for every provider, and
- is driven by a single model created through ``init_chat_model`` so Anthropic
  and OpenAI-compatible providers share one agentic loop.

The event consumer (:func:`process_events`) translates LangGraph
``astream_events`` into the ``trace_events`` schema, ``on_activity`` progress
callbacks, and result contract the UI, usage accounting, and export layers
expect.
"""

from __future__ import annotations

import json
import logging
import re
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

logger = logging.getLogger("deepagents_runtime")

# Fastfold skills intentionally use snake_case names (e.g. ``md_openmm_calvados``)
# that do not satisfy the stricter Agent Skills naming spec. They still load
# fine; silence the per-skill spec warnings to keep the CLI output clean while
# preserving genuine load errors.
logging.getLogger("deepagents.middleware.skills").setLevel(logging.ERROR)

# Leave headroom below the OpenAI 128-tool ceiling for deepagents' built-in
# tools (write_todos, filesystem ops, task, execute).
OPENAI_TOOL_BUDGET = 116
# Always keep sandbox / discovery tools when truncating for OpenAI.
_PINNED_TOOL_NAMES = (
    "run_python",
    "run_r",
    "shell_run",
    "search_tools",
    "sandbox_status",
    "sandbox_start",
    "sandbox_stop",
)


def provider_needs_openai_tool_cap(provider: str | None) -> bool:
    """Return True when the provider enforces OpenAI's ≤128 tools limit."""
    return str(provider or "").strip().lower() == "openai"


def finalize_tools_for_provider(tools: list, provider: str | None) -> list:
    """Apply provider-specific tool-list limits after domain + MCP assembly."""
    if not provider_needs_openai_tool_cap(provider):
        return list(tools)
    return _cap_tools_for_openai(tools)


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------

def build_chat_model(config, *, streaming: bool = True):
    """Create a LangChain chat model from Fastfold config via ``init_chat_model``.

    Supports ``anthropic``, ``openai`` (including OpenAI-compatible local
    endpoints), ``google`` via the native Google GenAI SDK, and other
    first-party OpenAI-compatible providers (xAI, NVIDIA, OpenCode Zen).
    """
    from langchain.chat_models import init_chat_model

    provider = str(config.get("llm.provider", "openai") or "openai").strip().lower()
    model = config.get("llm.model")
    temperature = float(config.get("llm.temperature", 0.1))

    if provider == "anthropic":
        from agent.model_catalog import (
            anthropic_model_omits_temperature,
            effective_anthropic_effort,
            get_model_reasoning,
            model_supports_reasoning_effort,
        )

        model = model or "claude-sonnet-4-5-20250929"
        kwargs: dict[str, Any] = {}
        if not anthropic_model_omits_temperature(model):
            kwargs["temperature"] = temperature
        api_key = config.llm_api_key("anthropic")
        if api_key:
            kwargs["api_key"] = api_key
        if model_supports_reasoning_effort("anthropic", model):
            effort, fast = get_model_reasoning(
                config.get("llm.model_reasoning"),
                "anthropic",
                model,
                default_effort=str(config.get("llm.reasoning_effort") or "medium"),
                default_fast=bool(config.get("llm.reasoning_fast", False)),
            )
            kwargs["effort"] = effective_anthropic_effort(effort=effort, fast=fast)
        return init_chat_model(f"anthropic:{model}", **kwargs)

    if provider == "openai":
        model = model or "gpt-5.6-sol"
        kwargs = {}
        # GPT-5 chat models reject a custom temperature; omit it for that family.
        if not str(model).strip().lower().startswith("gpt-5"):
            kwargs["temperature"] = temperature
        api_key = config.llm_api_key("openai")
        if api_key:
            kwargs["api_key"] = api_key
        base_url = config.llm_openai_base_url()
        if base_url:
            kwargs["base_url"] = base_url
        # Default to chat completions for OpenAI-compatible local endpoints
        # (Ollama, LM Studio, vLLM, ...). Codex + GPT-5.6 on OpenAI cloud need
        # Responses (tools + reasoning_effort are rejected on chat completions).
        from agent.config import Config
        from agent.model_catalog import (
            effective_reasoning_effort,
            get_model_reasoning,
            model_supports_reasoning_effort,
            openai_model_requires_responses_api,
        )

        is_openai_cloud = (not base_url) or Config._is_openai_managed_base_url(base_url)
        use_responses = bool(
            is_openai_cloud and openai_model_requires_responses_api(model)
        )
        kwargs["use_responses_api"] = use_responses
        if is_openai_cloud and model_supports_reasoning_effort("openai", model):
            effort, fast = get_model_reasoning(
                config.get("llm.model_reasoning"),
                "openai",
                model,
                default_effort=str(config.get("llm.reasoning_effort") or "medium"),
                default_fast=bool(config.get("llm.reasoning_fast", False)),
            )
            kwargs["reasoning_effort"] = effective_reasoning_effort(
                effort=effort,
                fast=fast,
                model_id=model,
            )
        return init_chat_model(f"openai:{model}", **kwargs)

    # Google Gemini must use the native GenAI SDK. Gemini 3+ requires
    # thought_signature to be echoed on tool-call turns; the OpenAI-compatible
    # Generative Language endpoint drops those and returns HTTP 400.
    if provider == "google":
        from agent.config import OPENAI_COMPATIBLE_PROVIDERS
        from agent.model_catalog import (
            effective_gemini_thinking_level,
            get_model_reasoning,
            google_model_supports_thinking_level,
            model_supports_reasoning_effort,
            resolve_catalog_model_id,
        )

        meta = OPENAI_COMPATIBLE_PROVIDERS.get("google", {})
        model = resolve_catalog_model_id(
            model or str(meta.get("default_model") or "gemini-3.5-flash")
        )
        kwargs: dict[str, Any] = {"temperature": temperature}
        api_key = config.llm_api_key("google")
        if api_key:
            kwargs["api_key"] = api_key
        if model_supports_reasoning_effort("google", model) or google_model_supports_thinking_level(
            model
        ):
            effort, fast = get_model_reasoning(
                config.get("llm.model_reasoning"),
                "google",
                model,
                default_effort=str(config.get("llm.reasoning_effort") or "medium"),
                default_fast=bool(config.get("llm.reasoning_fast", False)),
            )
            kwargs["thinking_level"] = effective_gemini_thinking_level(
                effort=effort, fast=fast
            )
        return init_chat_model(f"google_genai:{model}", **kwargs)

    # First-party OpenAI-compatible providers (xAI, NVIDIA, OpenCode Zen)
    # route through a fixed base URL + key. OpenCode Zen routes
    # GPT → Responses API, Claude/Qwen → Anthropic Messages, others → chat.
    from agent.config import OPENAI_COMPATIBLE_PROVIDERS
    from agent.model_catalog import (
        effective_reasoning_effort,
        effective_xai_reasoning_effort,
        get_model_reasoning,
        model_supports_reasoning_effort,
        opencode_anthropic_base_url,
        opencode_model_uses_anthropic,
        opencode_model_uses_responses_api,
    )

    base_url = config.llm_provider_base_url(provider)
    if base_url:
        meta = OPENAI_COMPATIBLE_PROVIDERS.get(provider, {})
        model = model or str(meta.get("default_model") or "")
        api_key = config.llm_api_key(provider)
        if provider == "opencode" and opencode_model_uses_anthropic(model):
            from agent.model_catalog import (
                anthropic_model_omits_temperature,
                effective_anthropic_effort,
            )

            kwargs = {}
            if not anthropic_model_omits_temperature(model):
                kwargs["temperature"] = temperature
            if api_key:
                kwargs["api_key"] = api_key
            kwargs["base_url"] = opencode_anthropic_base_url(base_url)
            if model_supports_reasoning_effort("opencode", model):
                effort, fast = get_model_reasoning(
                    config.get("llm.model_reasoning"),
                    "opencode",
                    model,
                    default_effort=str(config.get("llm.reasoning_effort") or "medium"),
                    default_fast=bool(config.get("llm.reasoning_fast", False)),
                )
                kwargs["effort"] = effective_anthropic_effort(
                    effort=effort, fast=fast
                )
            return init_chat_model(f"anthropic:{model}", **kwargs)
        kwargs = {}
        if not (
            provider == "opencode" and str(model).strip().lower().startswith("gpt-")
        ):
            kwargs["temperature"] = temperature
        if api_key:
            kwargs["api_key"] = api_key
        kwargs["base_url"] = base_url
        kwargs["use_responses_api"] = bool(
            provider == "opencode" and opencode_model_uses_responses_api(model)
        )
        if model_supports_reasoning_effort(provider, model):
            effort, fast = get_model_reasoning(
                config.get("llm.model_reasoning"),
                provider,
                model,
                default_effort=str(config.get("llm.reasoning_effort") or "medium"),
                default_fast=bool(config.get("llm.reasoning_fast", False)),
            )
            if provider == "xai":
                kwargs["reasoning_effort"] = effective_xai_reasoning_effort(
                    effort=effort,
                    fast=fast,
                    model_id=model,
                )
            else:
                kwargs["reasoning_effort"] = effective_reasoning_effort(
                    effort=effort,
                    fast=fast,
                    model_id=model,
                )
        return init_chat_model(f"openai:{model}", **kwargs)

    raise ValueError(
        f"deepagents runtime does not support llm.provider '{provider}'. "
        "Use 'anthropic', 'openai', 'xai', 'google', 'nvidia', or 'opencode'."
    )


# ---------------------------------------------------------------------------
# Skill sources (native progressive disclosure)
# ---------------------------------------------------------------------------

def skill_source_dirs() -> list[str]:
    """Return existing skill source directories for deepagents ``skills=``.

    Ordered low -> high priority (later sources win on name collision), mirroring
    :func:`agent.skills.iter_skills`: bundled -> npx -> global.

    Prefer :func:`resolve_skill_source_dirs` at runtime so Dashboard enable/disable
    and specialist allowlists are respected — this helper returns raw roots and
    will expose every on-disk skill to SkillsMiddleware.
    """
    from agent.skills import BUNDLED_SKILLS_DIR, GLOBAL_SKILLS_DIR, NPX_SKILLS_DIR

    sources: list[str] = []
    for path in (BUNDLED_SKILLS_DIR, NPX_SKILLS_DIR, GLOBAL_SKILLS_DIR):
        try:
            if path and Path(path).exists():
                sources.append(str(path))
        except Exception:  # noqa: BLE001
            continue
    return sources


def skill_source_dirs_for_names(skill_names: list[str]) -> list[str]:
    """Stage only the named skills into a temp directory for deepagents ``skills=``.

    When a specialist scopes a run, deepagents still expects parent directories that
    contain skill folders — so we symlink the selected skill directories into a
    staging root and return that root alone.
    """
    import hashlib
    import shutil
    import tempfile

    from agent.skills import skill_info

    names = [str(name).strip() for name in skill_names if str(name).strip()]
    if not names:
        return []

    resolved: list[tuple[str, Path]] = []
    for name in names:
        info = skill_info(name)
        if info is None:
            continue
        directory = info.directory
        if directory is None or not directory.is_dir():
            continue
        resolved.append((directory.name, directory.resolve()))

    if not resolved:
        return []

    stamp = hashlib.sha1(
        "|".join(sorted(f"{key}:{path}" for key, path in resolved)).encode()
    ).hexdigest()[:16]
    staging = Path(tempfile.gettempdir()) / "sandwalk-specialist-skills" / stamp
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    for key, directory in resolved:
        link = staging / key
        if link.exists() or link.is_symlink():
            link.unlink()
        try:
            link.symlink_to(directory, target_is_directory=True)
        except OSError:
            shutil.copytree(directory, link)
    return [str(staging)]


def resolve_skill_source_dirs(
    allowed_skill_names: list[str] | None = None,
) -> list[str]:
    """Skill roots for ``create_deep_agent(skills=...)``.

    Deep Agents loads skills with progressive disclosure: name + description at
    startup, full SKILL.md on demand
    (https://docs.langchain.com/oss/python/deepagents/overview#skills).

    - Specialist allowlist (``allowed_skill_names is not None``): stage those
      names only (empty list → no skills).
    - Default (None): stage **enabled** skills from the Skills UI — never the
      raw on-disk roots, which would ignore disable toggles.
    """
    from agent.skills import list_skills

    if allowed_skill_names is not None:
        return skill_source_dirs_for_names(list(allowed_skill_names or []))
    enabled = [s.name for s in list_skills(enabled_only=True)]
    return skill_source_dirs_for_names(enabled)


def build_skills_index_text(
    allowed_skill_names: list[str] | None = None,
) -> tuple[str, int]:
    """Build the progressive-disclosure skills catalog text Deep Agents injects.

    Mirrors ``SkillsMiddleware`` formatting (name, description, path hint) so
    Prompts estimates match first-turn input context.
    """
    from deepagents.middleware.skills import SKILLS_SYSTEM_PROMPT

    from agent.skills import list_skills, skill_info

    if allowed_skill_names is not None:
        skills = []
        for name in allowed_skill_names or []:
            info = skill_info(str(name).strip())
            if info is not None:
                skills.append(info)
    else:
        skills = list(list_skills(enabled_only=True))

    if not skills:
        body = "(No skills available yet.)"
    else:
        lines: list[str] = []
        for skill in skills:
            desc = str(getattr(skill, "description", "") or "").strip()
            path = getattr(skill, "directory", None)
            path_s = f"{path}/SKILL.md" if path else "SKILL.md"
            lines.append(f"- **{skill.name}**: {desc}")
            lines.append(f"  -> Read `{path_s}` for full instructions")
        body = "\n".join(lines)

    sources = resolve_skill_source_dirs(allowed_skill_names)
    locations = "\n".join(f"**Skills**: `{src}`" for src in sources) or "**Skills**: (none)"
    text = SKILLS_SYSTEM_PROMPT.format(
        skills_locations=locations,
        skills_load_warnings="",
        skills_list=body,
    )
    return text, len(skills)


def measure_deepagents_builtin_tool_schemas(
    *,
    domain_tools: list[Any],
    system_prompt: str,
    skills_sources: list[str],
    config: Any | None = None,
    workspace_root: str | None = None,
) -> tuple[str, list[str]]:
    """Return (schema_text, tool_names) for deepagents-injected builtins.

    Builds a real ``create_deep_agent`` graph (FakeListChatModel, no provider
    call) and reads ToolNode tools. Domain tools are excluded so Prompts can
    attribute filesystem / todos / task / execute separately.

    Per Deep Agents docs, input context = custom system prompt + BASE harness
    guidance + skills index + tool schemas
    (https://docs.langchain.com/oss/python/deepagents/context-engineering).
    """
    import tempfile

    from deepagents import create_deep_agent
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langgraph.prebuilt.tool_node import ToolNode

    from agent.sandbox_backend import resolve_deepagents_backend

    domain_names = {
        str(getattr(t, "name", "") or "")
        for t in domain_tools
        if getattr(t, "name", None)
    }
    model = FakeListChatModel(responses=["ok"])
    root = workspace_root or tempfile.mkdtemp(prefix="sandwalk-budget-")
    Path(root).mkdir(parents=True, exist_ok=True)

    handle = resolve_deepagents_backend(
        config,
        session_id="prompt-budget",
        workspace_root=root,
        skill_source_dirs=list(skills_sources or []),
        backend_override="builtin",
        sync_workspace=False,
    )
    agent = create_deep_agent(
        model=model,
        tools=list(domain_tools),
        system_prompt=system_prompt or "You are a helpful assistant.",
        skills=handle.skills_sources or (skills_sources or None),
        backend=handle.backend,
    )

    def _find_toolnodes(
        obj: Any, seen: set[int] | None = None, depth: int = 0
    ) -> list[Any]:
        if seen is None:
            seen = set()
        if obj is None or id(obj) in seen or depth > 10:
            return []
        seen.add(id(obj))
        if isinstance(obj, ToolNode):
            return [obj]
        found: list[Any] = []
        if isinstance(obj, dict):
            for value in obj.values():
                found.extend(_find_toolnodes(value, seen, depth + 1))
            return found
        if isinstance(obj, (list, tuple)):
            for value in obj:
                found.extend(_find_toolnodes(value, seen, depth + 1))
            return found
        for attr in (
            "nodes",
            "bound",
            "runnable",
            "tools_by_name",
            "node",
            "afunc",
            "func",
            "_func",
        ):
            if hasattr(obj, attr):
                try:
                    found.extend(_find_toolnodes(getattr(obj, attr), seen, depth + 1))
                except Exception:  # noqa: BLE001
                    continue
        return found

    tools_by_name: dict[str, Any] = {}
    for node in _find_toolnodes(agent):
        mapping = getattr(node, "tools_by_name", None) or {}
        if isinstance(mapping, dict):
            tools_by_name.update(mapping)

    builtin = [
        tool
        for name, tool in sorted(tools_by_name.items())
        if name and name not in domain_names
    ]

    def _schema_text(tool: Any) -> str:
        name = str(getattr(tool, "name", "") or "")
        description = str(getattr(tool, "description", "") or "")
        schema: Any = {}
        args_schema = getattr(tool, "args_schema", None)
        if args_schema is not None:
            try:
                if hasattr(args_schema, "model_json_schema"):
                    schema = args_schema.model_json_schema()
                elif isinstance(args_schema, dict):
                    schema = args_schema
            except Exception:  # noqa: BLE001
                schema = {}
        try:
            schema_text = json.dumps(schema, ensure_ascii=True, default=str)
        except Exception:  # noqa: BLE001
            schema_text = str(schema)
        return f"{name}\n{description}\n{schema_text}"

    text = "\n\n".join(_schema_text(t) for t in builtin)
    return text, [str(getattr(t, "name", "") or "") for t in builtin]


async def create_external_mcp_tools(servers: list[dict] | None) -> list[Any]:
    """Load tools from enabled stdio/SSE/streamable-HTTP MCP servers.

    Aligns with langchain-mcp-adapters / Deep Agents Code connection shape:
    stdio ``command``+``args``(+optional ``env``), remote ``url``+``headers``,
    transport aliases ``http`` / ``streamable-http`` → ``streamable_http``.
    """
    if not servers:
        return []
    from langchain_mcp_adapters.client import MultiServerMCPClient

    connections: dict[str, dict[str, Any]] = {}
    for server in servers:
        if not server.get("enabled", True):
            continue
        name = str(server.get("name") or server.get("id") or "").strip()
        raw_transport = str(
            server.get("transport") or server.get("type") or ""
        ).strip().lower().replace("-", "_")
        if raw_transport in {"http", "streamable_http", "streamablehttp"}:
            transport = "streamable_http"
        elif raw_transport in {"sse", "stdio"}:
            transport = raw_transport
        else:
            continue
        if not name:
            continue
        if transport == "stdio":
            command = str(server.get("command") or "").strip()
            if not command:
                continue
            connection: dict[str, Any] = {
                "transport": "stdio",
                "command": command,
                "args": [str(arg) for arg in server.get("args") or []],
            }
            env = server.get("env")
            if isinstance(env, dict) and env:
                connection["env"] = {str(k): str(v) for k, v in env.items()}
            connections[name] = connection
        else:
            url = str(server.get("url") or "").strip()
            if not url:
                continue
            connection = {
                "transport": transport,
                "url": url,
            }
            headers = server.get("headers")
            if isinstance(headers, dict) and headers:
                connection["headers"] = {
                    str(key): str(value) for key, value in headers.items()
                }
            connections[name] = connection
    if not connections:
        return []
    client = MultiServerMCPClient(connections)
    return list(await client.get_tools())


# ---------------------------------------------------------------------------
# Tool adapter: registry tools -> LangChain StructuredTool
# ---------------------------------------------------------------------------

def _sanitize_tool_name(name: str) -> str:
    """Produce a provider-safe tool name (``^[A-Za-z0-9_-]+``)."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", str(name or "").strip())
    return cleaned or "tool"


def _args_schema_for(model_name: str, parameters: dict | None, *, required_code: bool = False):
    """Build a pydantic args schema mirroring the MCP string-typed schema.

    Parameter names that are not valid Python identifiers are skipped (the
    model could not address them anyway); ``protected_namespaces`` is disabled
    so params like ``model`` / ``schema`` do not raise pydantic warnings.
    """
    from pydantic import ConfigDict, Field, create_model

    fields: dict[str, Any] = {}
    if required_code:
        fields["code"] = (str, Field(description="Code to execute"))
    for pname, desc in (parameters or {}).items():
        key = str(pname)
        if not key.isidentifier() or key.startswith("_") or key == "code":
            continue
        fields[key] = (str | None, Field(default=None, description=str(desc)))

    config = ConfigDict(protected_namespaces=())
    try:
        return create_model(f"{model_name}_Args", __config__=config, **fields)
    except Exception:  # noqa: BLE001 - fall back to an arg-less schema
        return create_model(f"{model_name}_Args", __config__=config)


def _make_lc_tool(*, name: str, description: str, args_schema, handler, strip_none: bool = True):
    """Wrap an async ``mcp_server`` handler as a LangChain ``StructuredTool``."""
    from langchain_core.tools import StructuredTool

    async def _coroutine(**kwargs):
        args = {
            key: value
            for key, value in kwargs.items()
            if value is not None or not strip_none
        }
        result = await handler(args)
        parts = result.get("content", []) if isinstance(result, dict) else []
        text = "\n".join(
            str(part.get("text", ""))
            for part in parts
            if isinstance(part, dict) and part.get("type") == "text"
        )
        return text or "(no output)"

    def _sync_unsupported(**_kwargs):  # pragma: no cover - deepagents runs async
        raise NotImplementedError("This tool is async-only; call via ainvoke.")

    return StructuredTool(
        name=name,
        description=description or name,
        args_schema=args_schema,
        func=_sync_unsupported,
        coroutine=_coroutine,
    )


def _cap_tools_for_openai(tools: list, max_total: int = OPENAI_TOOL_BUDGET) -> list:
    """Cap the domain tool list for OpenAI while keeping the sandbox tools."""
    if len(tools) <= max_total:
        return list(tools)

    by_name = {getattr(t, "name", ""): t for t in tools}
    selected = list(tools[:max_total])
    selected_names = {getattr(t, "name", "") for t in selected}

    for pinned in _PINNED_TOOL_NAMES:
        spec = by_name.get(pinned)
        if spec is None or pinned in selected_names:
            continue
        replace_idx = next(
            (
                idx
                for idx in range(len(selected) - 1, -1, -1)
                if getattr(selected[idx], "name", "") not in _PINNED_TOOL_NAMES
            ),
            None,
        )
        if replace_idx is not None:
            selected_names.discard(getattr(selected[replace_idx], "name", ""))
            selected[replace_idx] = spec
            selected_names.add(pinned)
    return selected


def _make_search_tools_tool(exclude_categories: set[str], exclude_tools: set[str]):
    """Build the on-demand ``search_tools`` StructuredTool used in PTC mode."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, ConfigDict, Field

    from agent.ptc_tools import search_tools_text

    class SearchToolsArgs(BaseModel):
        model_config = ConfigDict(protected_namespaces=())
        query: str = Field(description="Keywords describing the tool you need")
        category: str | None = Field(
            default=None, description="Optional category to restrict the search"
        )
        limit: int | None = Field(default=12, description="Max results (default 12)")

    async def _coroutine(query: str, category: str | None = None, limit: int | None = 12):
        return search_tools_text(
            query,
            category=category,
            limit=int(limit or 12),
            exclude_categories=exclude_categories,
            exclude_tools=exclude_tools,
        )

    def _sync_unsupported(**_kwargs):  # pragma: no cover - deepagents runs async
        raise NotImplementedError("This tool is async-only; call via ainvoke.")

    return StructuredTool(
        name="search_tools",
        description=(
            "Search the domain-tool catalog and return exact call signatures "
            "(tools.<category>.<name>(params) -> dict) for tools matching a query. "
            "Use before calling an unfamiliar domain tool inside run_python."
        ),
        args_schema=SearchToolsArgs,
        func=_sync_unsupported,
        coroutine=_coroutine,
    )


def create_ct_langchain_tools(
    session,
    *,
    exclude_categories: set[str] | None = None,
    exclude_tools: set[str] | None = None,
    include_run_python: bool = True,
    provider: str = "anthropic",
    tool_mode: str = "native",
    session_id: str | None = None,
) -> tuple[list, Any, list[dict], dict[str, str]]:
    """Build LangChain tools for the deepagents graph from the ct registry.

    ``tool_mode`` selects the strategy:

    - ``"native"`` (default): every domain tool is exposed as its own
      ``StructuredTool`` schema.
    - ``"ptc"``: Programmatic Tool Calling. Domain tools are injected as Python
      callables into the run_python sandbox (the model calls them in code), so
      only ``run_python``/``run_r``/``shell_run``/``search_tools`` are exposed as
      tool schemas. This sharply reduces per-call input tokens and removes the
      OpenAI tool-count ceiling.

    Returns ``(tools, sandbox, code_trace_buffer, display_name_map)`` where
    ``display_name_map`` maps the sanitized (provider-safe) tool name back to
    the original dotted name for trace rendering.
    """
    from agent.mcp_server import (
        _make_run_python_handler,
        _make_run_r_handler,
        _make_tool_handler,
    )
    from tools import EXPERIMENTAL_CATEGORIES, ensure_loaded, registry

    ensure_loaded()
    exclude_categories = exclude_categories or set()
    exclude_tools = exclude_tools or set()
    code_trace_buffer: list[dict] = []

    tools: list = []
    display_name_map: dict[str, str] = {}
    used_names: set[str] = set()

    def _unique(name: str) -> str:
        candidate = _sanitize_tool_name(name)
        base = candidate
        i = 2
        while candidate in used_names:
            candidate = f"{base}_{i}"
            i += 1
        used_names.add(candidate)
        return candidate

    ptc = str(tool_mode).strip().lower() == "ptc"
    tools_namespace = None

    if ptc:
        from agent.ptc_tools import build_tools_namespace

        ptc_excludes = set(exclude_categories) | set(EXPERIMENTAL_CATEGORIES)
        tools_namespace = build_tools_namespace(
            session, exclude_categories=ptc_excludes, exclude_tools=exclude_tools
        )

        used_names.add("search_tools")
        display_name_map["search_tools"] = "search_tools"
        tools.append(_make_search_tools_tool(ptc_excludes, set(exclude_tools)))

        # Expose shell.run as a first-class tool so skills can run scripts
        # directly (rather than wrapping every command in run_python).
        shell_obj = registry.get_tool("shell.run")
        if shell_obj is not None:
            safe_name = _unique(shell_obj.name)
            display_name_map[safe_name] = shell_obj.name
            tools.append(
                _make_lc_tool(
                    name=safe_name,
                    description=shell_obj.description or shell_obj.name,
                    args_schema=_args_schema_for(safe_name, shell_obj.parameters),
                    handler=_make_tool_handler(shell_obj, session),
                )
            )
    else:
        for tool_obj in registry.list_tools():
            if tool_obj.category in exclude_categories:
                continue
            if tool_obj.name in exclude_tools:
                continue
            if tool_obj.category in EXPERIMENTAL_CATEGORIES:
                continue

            safe_name = _unique(tool_obj.name)
            display_name_map[safe_name] = tool_obj.name
            description = tool_obj.description or tool_obj.name
            if getattr(tool_obj, "usage_guide", ""):
                description = f"{description}\nUSE WHEN: {tool_obj.usage_guide}"[:1024]

            tools.append(
                _make_lc_tool(
                    name=safe_name,
                    description=description,
                    args_schema=_args_schema_for(safe_name, tool_obj.parameters),
                    handler=_make_tool_handler(tool_obj, session),
                )
            )

    sandbox = None
    if include_run_python:
        rp_handler, sandbox = _make_run_python_handler(
            session,
            code_trace_buffer,
            tools_namespace=tools_namespace,
            session_id=session_id,
        )
        display_name_map["run_python"] = "run_python"
        used_names.add("run_python")
        rp_description = (
            "Execute Python code in a persistent sandbox. Variables persist "
            "between calls on the host CT sandbox. Pre-imported on host: pd, np, "
            "plt, sns, scipy_stats, sklearn, json, re, math, Path, "
            "safe_subprocess_run. Save plots to OUTPUT_DIR. When done, assign "
            "result = {'summary': '...', 'answer': '...'}. "
            "IMPORTANT: when a Modal sandbox is attached for this chat, general "
            "Python (no tools.* calls) is executed inside Modal under /workspace "
            "(remote Linux). Code that calls tools.<category>.<name>(...) stays "
            "on the host. Prefer /workspace paths for Modal runs; do not mkdir "
            "/workspace on the host."
        )
        if ptc:
            rp_description += (
                " The full domain-tool library is pre-bound as `tools` — call "
                "tools.<category>.<name>(**kwargs) -> dict and process results here; "
                "only what you print returns. Use tools.search('...') or the "
                "search_tools tool to find signatures. Domain-tool calls always "
                "run on the host even when Modal is attached."
            )
        tools.append(
            _make_lc_tool(
                name="run_python",
                description=rp_description,
                args_schema=_args_schema_for("run_python", None, required_code=True),
                handler=rp_handler,
                strip_none=False,
            )
        )

        try:
            import importlib.util

            if importlib.util.find_spec("rpy2.robjects") is None:
                raise ImportError("rpy2 unavailable")
            rr_handler = _make_run_r_handler(code_trace_buffer)
            display_name_map["run_r"] = "run_r"
            used_names.add("run_r")
            tools.append(
                _make_lc_tool(
                    name="run_r",
                    description=(
                        "Execute R code via rpy2 for statistical workflows (splines, "
                        "p.adjust, wilcox.test, fisher.test, lm/predict, KEGGREST)."
                    ),
                    args_schema=_args_schema_for("run_r", None, required_code=True),
                    handler=rr_handler,
                    strip_none=False,
                )
            )
        except ImportError:
            logger.info("rpy2 not available — run_r tool disabled")

    # Soft-cap native fan-out early so traces stay small; runner still applies
    # ``finalize_tools_for_provider`` after MCP tools are merged (Neurosnap
    # alone can exceed OpenAI's 128-tool limit).
    if not ptc and provider_needs_openai_tool_cap(provider):
        tools = _cap_tools_for_openai(tools)

    return tools, sandbox, code_trace_buffer, display_name_map


# ---------------------------------------------------------------------------
# Event consumer: astream_events(v2) -> trace_events + progress
# ---------------------------------------------------------------------------

def _text_from_content(content: Any) -> str:
    """Extract plain text from a LangChain message content (str or blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return ""


def _tool_output_text(output: Any) -> str:
    """Normalize a tool-end output (ToolMessage / str / list) to text."""
    content = getattr(output, "content", output)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def _usage_from_message(message: Any) -> dict[str, int] | None:
    """Read LangChain ``usage_metadata`` into the ct token-usage shape."""
    usage = getattr(message, "usage_metadata", None)
    if not isinstance(usage, dict):
        return None
    details = usage.get("input_token_details") or {}
    return {
        "input_tokens": int(usage.get("input_tokens", 0) or 0),
        "output_tokens": int(usage.get("output_tokens", 0) or 0),
        "cache_creation_input_tokens": int(details.get("cache_creation", 0) or 0),
        "cache_read_input_tokens": int(details.get("cache_read", 0) or 0),
    }


async def process_events(
    events_iter,
    *,
    trace_renderer=None,
    headless: bool = False,
    trace_events: list[dict] | None = None,
    thinking_status=None,
    allow_live_spinner: bool = True,
    runner=None,
    on_activity=None,
    code_trace_buffer: list[dict] | None = None,
    display_name_map: dict[str, str] | None = None,
    group_tools: bool = True,
    tool_detail_limit: int = 8,
) -> dict:
    """Consume ``astream_events`` (v2) into the ct result/trace contract.

    Produces the ExecutionResult, trace export, and usage-accounting shapes the
    UI and export layers expect.

    Tool-call rendering: when ``group_tools`` is True, the most recent
    ``tool_detail_limit`` tools in a consecutive batch are shown in full (name,
    args, output) and older ones collapse progressively to a one-line, still
    named ``✓ name (Xs)`` entry as newer tools complete — so the current/last
    call stays detailed while earlier ones compact away. Errors are always shown
    in full. Todos render as a checklist and the batch flushes whenever the
    assistant writes text. Set ``group_tools`` False to show every tool in full.
    """
    display_name_map = display_name_map or {}
    full_text: list[str] = []
    tool_calls: list[dict] = []
    inflight: dict[str, dict] = {}
    streamed_len = 0
    model_call_count = 0
    code_cursor = 0
    spinner = {"obj": thinking_status}
    group = {"active": False, "count": 0, "errors": 0, "start": 0.0}
    # Trailing-detail buffer: the most recent `detail_window` completed tools are
    # held back and shown in full; as newer tools complete, older ones spill out
    # of the window and are flushed as compact, still-named lines.
    pending: list[dict] = []
    detail_window = max(1, int(tool_detail_limit))
    token_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }

    def _emit_progress(event: str, **payload) -> None:
        if not on_activity:
            return
        try:
            on_activity(event, **payload)
            return
        except TypeError:
            pass
        except Exception:
            return
        if event == "activity":
            text = str(payload.get("text") or "").strip()
            if text:
                with suppress(Exception):
                    on_activity(text)

    def _stop_spinner() -> None:
        if spinner["obj"] is not None:
            with suppress(Exception):
                spinner["obj"].stop()
            spinner["obj"] = None
            if runner is not None:
                runner._active_spinner = None

    def _start_evaluating_spinner() -> None:
        if not allow_live_spinner or headless or trace_renderer is None:
            return
        if spinner["obj"] is not None:
            return
        try:
            from ui.status import ThinkingStatus

            status = ThinkingStatus(trace_renderer.console, phase="evaluating")
            status.__enter__()
            status.start_async_refresh()
            spinner["obj"] = status
            if runner is not None:
                runner._active_spinner = status
        except Exception:  # noqa: BLE001
            pass

    def _add_usage(message: Any) -> None:
        totals = _usage_from_message(message)
        if not totals:
            return
        changed = False
        for key, value in totals.items():
            if value > 0:
                token_usage[key] = int(token_usage.get(key, 0)) + int(value)
                changed = True
        if changed:
            _emit_progress(
                "usage",
                input_tokens=int(token_usage["input_tokens"]),
                output_tokens=int(token_usage["output_tokens"]),
                cache_creation_input_tokens=int(token_usage["cache_creation_input_tokens"]),
                cache_read_input_tokens=int(token_usage["cache_read_input_tokens"]),
            )

    def _flush_one(item: dict, *, full: bool) -> None:
        """Render one buffered tool result, full or compact (errors always full)."""
        if headless or trace_renderer is None:
            return
        name = item.get("name") or "unknown"
        if full or item.get("is_error"):
            if item.get("is_error"):
                trace_renderer.render_tool_error(name, item.get("result_text", ""))
            else:
                trace_renderer.render_tool_complete(
                    name,
                    item.get("input") or {},
                    item.get("result_text", ""),
                    float(item.get("duration", 0.0)),
                )
        else:
            from ui.traces import format_duration

            dur = format_duration(float(item.get("duration", 0.0)))
            trace_renderer.console.print(
                f"  [green]\u2713[/] [dim]{name} ({dur})[/]"
            )

    def _close_group() -> None:
        """Flush any buffered tools in full detail and reset the batch state."""
        while pending:
            _flush_one(pending.pop(0), full=True)
        if not group["active"]:
            return
        group.update({"active": False, "count": 0, "errors": 0, "start": 0.0})

    async for event in events_iter:
        etype = event.get("event", "")
        data = event.get("data", {}) or {}

        if etype == "on_chat_model_stream":
            chunk = data.get("chunk")
            text = _text_from_content(getattr(chunk, "content", "")) if chunk is not None else ""
            if text:
                if group_tools:
                    _close_group()
                _stop_spinner()
                streamed_len += len(text)
                _emit_progress(
                    "stream",
                    delta=text,
                    streamed_chars=int(streamed_len),
                )
            continue

        if etype == "on_chat_model_end":
            model_call_count += 1
            output = data.get("output")
            _add_usage(output)
            text = _text_from_content(getattr(output, "content", "")) if output is not None else ""
            if text.strip():
                if group_tools:
                    _close_group()
                _stop_spinner()
                full_text.append(text)
                if trace_events is not None:
                    trace_events.append(
                        {"type": "text", "content": text, "timestamp": time.time()}
                    )
                if not headless and trace_renderer:
                    streamed_len = 0
                    trace_renderer.render_reasoning(text)
                snippet = text.strip().replace("\n", " ")[:40]
                if snippet:
                    _emit_progress("activity", text=snippet)
            continue

        if etype == "on_tool_start":
            raw_name = event.get("name", "") or ""
            display = display_name_map.get(raw_name, raw_name)
            run_id = event.get("run_id", "") or ""
            tool_input = data.get("input", {}) or {}
            now = time.time()
            _stop_spinner()
            inflight[run_id] = {"name": display, "input": tool_input, "start_time": now}
            tool_calls.append({"name": display, "input": tool_input})
            _emit_progress(
                "tool_start",
                name=display,
                arguments=tool_input,
                tool_call_id=run_id,
            )
            if trace_events is not None:
                trace_events.append(
                    {
                        "type": "tool_start",
                        "tool": display,
                        "input": tool_input,
                        "tool_use_id": run_id,
                        "timestamp": now,
                    }
                )
            is_todos = display == "write_todos"
            if group_tools and not is_todos:
                # Detail is deferred to tool-end (trailing window), so the
                # current call surfaces live via the spinner/toolbar instead of a
                # start line that we'd be unable to collapse later.
                if not group["active"]:
                    group.update({"active": True, "count": 0, "errors": 0, "start": now})
                group["count"] = int(group["count"]) + 1
                _emit_progress("activity", text=f"\u25b8 {display}")
                _start_evaluating_spinner()
                continue

            if not headless and trace_renderer:
                if is_todos:
                    # Todos stay visible; close any open group first so the
                    # checklist isn't swallowed by the collapsed summary.
                    if group_tools:
                        _close_group()
                    trace_renderer.render_todos(tool_input.get("todos"))
                else:
                    trace_renderer.render_tool_start(display, tool_input)
            _emit_progress("activity", text=f"\u25b8 {display}")
            _start_evaluating_spinner()
            continue

        if etype == "on_tool_end":
            raw_name = event.get("name", "") or ""
            display = display_name_map.get(raw_name, raw_name)
            run_id = event.get("run_id", "") or ""
            output = data.get("output")
            result_text = _tool_output_text(output)
            is_error = str(getattr(output, "status", "") or "").lower() == "error"

            tracked = inflight.pop(run_id, None)
            duration = 0.0
            tool_input: dict = {}
            if tracked:
                duration = max(0.0, time.time() - tracked["start_time"])
                display = tracked["name"]
                tool_input = tracked["input"]
            _stop_spinner()
            _emit_progress(
                "tool_end",
                name=display,
                output=result_text,
                is_error=is_error,
                duration_s=duration,
                tool_call_id=run_id,
            )

            for entry in reversed(tool_calls):
                if entry.get("name") == display and "result_text" not in entry:
                    entry["result_text"] = result_text
                    entry["duration_s"] = duration
                    break

            if trace_events is not None:
                evt = {
                    "type": "tool_result",
                    "tool": display,
                    "tool_use_id": run_id,
                    "result_text": result_text,
                    "is_error": is_error,
                    "duration_s": duration,
                    "timestamp": time.time(),
                }
                if display in ("run_python", "run_r") and code_trace_buffer is not None:
                    if code_cursor < len(code_trace_buffer):
                        meta = code_trace_buffer[code_cursor]
                        code_cursor += 1
                        evt.update(
                            {
                                "result_text": meta.get("stdout", result_text),
                                "is_error": bool(meta.get("error")),
                                "code": meta.get("code", ""),
                                "stdout": meta.get("stdout", ""),
                                "plots": meta.get("plots", []),
                                "exports": meta.get("exports", []),
                                "error": meta.get("error"),
                            }
                        )
                trace_events.append(evt)

            if group_tools and display != "write_todos":
                if is_error:
                    group["errors"] = int(group["errors"]) + 1
                # Buffer this result as the new "current" full-detail call; spill
                # anything older than the trailing window out as a compact line.
                pending.append(
                    {
                        "name": display or "unknown",
                        "input": tool_input,
                        "result_text": result_text,
                        "duration": duration,
                        "is_error": is_error,
                    }
                )
                while len(pending) > detail_window:
                    _flush_one(pending.pop(0), full=False)
                _emit_progress("activity", text=f"\u25b8 {display}")
                continue

            if not headless and trace_renderer:
                if display == "write_todos":
                    # The checklist was already rendered at tool-start; the raw
                    # Command(update=...) echo would just add noise.
                    pass
                elif is_error:
                    trace_renderer.render_tool_error(display or "unknown", result_text)
                else:
                    trace_renderer.render_tool_complete(
                        display or "unknown", tool_input, result_text, duration
                    )
            continue

    if group_tools:
        _close_group()
    _stop_spinner()

    return {
        "full_text": full_text,
        "tool_calls": tool_calls,
        "token_usage": token_usage,
        "model_call_count": model_call_count,
        "pending_background_tasks": [],
        "completed_background_tasks": [],
    }
