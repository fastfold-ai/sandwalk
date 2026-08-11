"""Unit tests for Modal sandbox container creation (Modal SDK mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def test_create_modal_sandbox_forwards_modal_tokens_into_container(monkeypatch):
    """The container itself must get MODAL_TOKEN_ID/SECRET too.

    Otherwise `modal` CLI calls made *inside* the sandbox (e.g. by the
    modal-gpu-dev / modal-gpu-experiment skills, or the deepagents native
    `execute` tool) fail to authenticate even though the agent-server's own
    process env is already synced for the control-plane call that creates
    the sandbox.
    """
    from agent.sandbox_backend.lifecycle import _create_or_reuse_modal_sandbox_impl

    monkeypatch.setenv("MODAL_TOKEN_ID", "ak-test-id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "as-test-secret")

    fake_modal = MagicMock()
    fake_modal.App.lookup.return_value = MagicMock()
    fake_modal.Sandbox.from_name.side_effect = Exception("no existing sandbox")
    created_sandbox = MagicMock()
    fake_modal.Sandbox.create.return_value = created_sandbox

    fake_modal_sandbox_cls = MagicMock()
    fake_modal_sandbox_cls.return_value = SimpleNamespace(
        execute=lambda *a, **k: None
    )

    cfg = SimpleNamespace(
        get=lambda key, default=None: {
            "sandbox.modal_app": "sandwalk-test",
            "sandbox.idle_ttl_seconds": 600,
            "sandbox.timeout": 30,
            "sandbox.cpu_cores": 1.0,
            "sandbox.ram_gb": 2.0,
            "sandbox.compute_type": "cpu",
        }.get(key, default)
    )

    with (
        patch("agent.sandbox_deps.require_modal_deps"),
        patch("agent.sandbox_backend.image._build_modal_image", return_value=MagicMock()),
        patch.dict(
            "sys.modules",
            {
                "modal": fake_modal,
                "langchain_modal": SimpleNamespace(ModalSandbox=fake_modal_sandbox_cls),
            },
        ),
    ):
        _create_or_reuse_modal_sandbox_impl(cfg, session_id="s-env-test")

    assert fake_modal.Sandbox.create.called
    _, kwargs = fake_modal.Sandbox.create.call_args
    assert kwargs.get("env") == {
        "MODAL_TOKEN_ID": "ak-test-id",
        "MODAL_TOKEN_SECRET": "as-test-secret",
    }
