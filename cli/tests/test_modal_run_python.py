"""Tests for Modal-aware run_python routing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from agent.modal_run_python import (
    code_requires_host_runtime,
    execute_python_on_modal,
    rewrite_modal_workspace_paths,
    try_modal_run_python,
)


def test_code_requires_host_runtime_detects_tools_namespace():
    assert code_requires_host_runtime("x = tools.chemistry.descriptors(smiles='C')")
    assert code_requires_host_runtime("print(tools.search('fold'))")
    assert not code_requires_host_runtime("print(Path('/workspace') / 'a')")
    assert not code_requires_host_runtime("import numpy as np\nprint(np.pi)")


def test_rewrite_modal_workspace_paths():
    host = "/Users/me/.sandwalk/workspaces/abc"
    code = "out = Path('/workspace/artifacts')\nprint('/workspace')"
    rewritten = rewrite_modal_workspace_paths(code, host)
    assert host in rewritten
    assert "'/workspace'" not in rewritten
    assert f"'{host}'" in rewritten or f'"{host}"' in rewritten


def test_try_modal_run_python_skips_without_session():
    assert try_modal_run_python(session_id=None, code="print(1)") is None


def test_try_modal_run_python_skips_ptc_code(monkeypatch):
    handle = SimpleNamespace(kind="modal", backend=MagicMock())
    monkeypatch.setattr(
        "agent.sandbox_backend.get_active_handle",
        lambda _sid: handle,
    )
    assert (
        try_modal_run_python(
            session_id="s1",
            code="print(tools.literature.pubmed_search(query='egfr'))",
        )
        is None
    )


def test_try_modal_run_python_routes_general_code(monkeypatch):
    inner = MagicMock()
    inner.execute.return_value = SimpleNamespace(
        output="hello from modal\n",
        exit_code=0,
    )
    handle = SimpleNamespace(
        kind="modal",
        backend=SimpleNamespace(default=inner),
    )
    monkeypatch.setattr(
        "agent.sandbox_backend.get_active_handle",
        lambda _sid: handle,
    )
    result = try_modal_run_python(session_id="s1", code="print('hello from modal')")
    assert result is not None
    assert result["runtime"] == "modal"
    assert result["error"] is None
    assert "Modal" in result["stdout"]
    assert "hello from modal" in result["stdout"]
    inner.execute.assert_called_once()
    cmd = inner.execute.call_args[0][0]
    assert "/workspace" in cmd
    assert "_run_python.py" in cmd


def test_execute_python_on_modal_nonzero_exit():
    inner = MagicMock()
    inner.execute.return_value = SimpleNamespace(
        output="Traceback: boom",
        exit_code=1,
    )
    handle = SimpleNamespace(kind="modal", backend=SimpleNamespace(default=inner))
    result = execute_python_on_modal(handle, "raise SystemExit(1)")
    assert result["runtime"] == "modal"
    assert result["error"]
    assert "boom" in result["error"] or "exited" in result["error"]
