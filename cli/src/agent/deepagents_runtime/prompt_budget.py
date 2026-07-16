"""Measure deepagents-injected builtin tool schemas for the prompt-budget estimator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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
