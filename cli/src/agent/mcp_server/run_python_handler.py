"""The run_python MCP tool handler: persistent Sandbox + optional Modal routing."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("mcp_server")


def _make_run_python_handler(
    session,
    code_trace_buffer: list | None = None,
    tools_namespace=None,
    session_id: str | None = None,
):
    """Create the run_python MCP tool handler with a persistent Sandbox.

    The sandbox is created lazily on first invocation and persists across
    tool calls within one query (variables carry over). A new MCP server
    (and thus a new sandbox) is created for each query, so state resets
    between queries automatically.

    When a Modal sandbox is attached for ``session_id``, general Python
    (code that does not call ``tools.*``) is routed into Modal under
    ``/workspace``. PTC ``tools.*`` calls stay on the host CT sandbox.

    Args:
        session: Active ct Session.
        code_trace_buffer: Optional shared list. When provided, the handler
            appends structured execution metadata after each call. This
            bypasses the SDK message stream (which may truncate tool results)
            so the trace collector gets full code, stdout, and plot data.
        tools_namespace: Optional Programmatic Tool Calling (PTC) namespace of
            domain-tool callables to bind as ``tools`` in the sandbox. See
            :mod:`agent.ptc_tools`.
        session_id: Chat session id used to resolve an attached Modal handle.
    """
    from agent.modal_run_python import (
        rewrite_modal_workspace_paths,
        try_modal_run_python,
    )
    from agent.sandbox import Sandbox
    from agent.sandbox_backend import get_active_handle

    config = session.config
    timeout = int(config.get("sandbox.timeout", 300))
    output_dir = config.get("sandbox.output_dir")
    max_retries = int(config.get("sandbox.max_retries", 2))
    sid = str(session_id or "").strip() or None

    extra_read_dirs = []
    extra_read_str = config.get("sandbox.extra_read_dirs")
    if extra_read_str:
        for d in str(extra_read_str).split(","):
            d = d.strip()
            if d and Path(d).exists():
                extra_read_dirs.append(Path(d))

    sandbox = Sandbox(
        timeout=timeout,
        output_dir=output_dir,
        max_retries=max_retries,
        extra_read_dirs=extra_read_dirs or None,
    )
    sandbox.load_datasets()
    if tools_namespace is not None:
        sandbox.inject_tools(tools_namespace)

    def _host_workspace_root() -> str:
        import os

        env = str(os.environ.get("SANDWALK_SESSION_WORKSPACE") or "").strip()
        if env:
            return env
        if sid:
            handle = get_active_handle(sid)
            if handle is not None and getattr(handle, "workspace_root", None):
                return str(handle.workspace_root)
        return ""

    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        code = args.get("code", "")
        if not code.strip():
            return {
                "content": [{"type": "text", "text": "Error: no code provided"}],
                "is_error": True,
            }

        exec_result = await asyncio.to_thread(
            try_modal_run_python,
            session_id=sid,
            code=code,
            timeout=timeout,
        )
        if exec_result is None:
            host_root = _host_workspace_root()
            host_code = (
                rewrite_modal_workspace_paths(code, host_root) if host_root else code
            )
            if host_code != code:
                logger.info(
                    "Rewrote /workspace → host session path for host run_python"
                )
            exec_result = await asyncio.to_thread(sandbox.execute, host_code)
            exec_result = {
                **exec_result,
                "runtime": exec_result.get("runtime") or "host",
            }

        # Build output text
        parts = []
        if exec_result.get("stdout"):
            parts.append(exec_result["stdout"])
        if exec_result.get("error"):
            parts.append(f"Error:\n{exec_result['error']}")
        if exec_result.get("plots"):
            parts.append(f"Plots saved: {exec_result['plots']}")
        if exec_result.get("exports"):
            parts.append(f"Exports saved: {exec_result['exports']}")

        # Check if the code set a `result` variable (host sandbox only)
        if exec_result.get("runtime") != "modal":
            result_var = sandbox.get_variable("result")
            if result_var and isinstance(result_var, dict):
                summary = result_var.get("summary", "")
                answer = result_var.get("answer", "")
                if summary:
                    parts.append(f"\nResult summary: {summary}")
                if answer:
                    parts.append(f"Result answer: {answer}")

        text = "\n".join(parts) if parts else "(no output)"
        # Cap output to keep context manageable
        text = text[:6000]

        # Buffer structured execution metadata for trace capture.
        # This bypasses the SDK stream which may truncate tool results.
        if code_trace_buffer is not None:
            code_trace_buffer.append({
                "tool": "run_python",
                "code": code,
                "stdout": exec_result.get("stdout", ""),
                "plots": exec_result.get("plots", []),
                "exports": exec_result.get("exports", []),
                "error": exec_result.get("error"),
                "runtime": exec_result.get("runtime"),
            })

        is_error = bool(exec_result.get("error"))
        return {
            "content": [{"type": "text", "text": text}],
            "is_error": is_error,
        }

    return handler, sandbox
