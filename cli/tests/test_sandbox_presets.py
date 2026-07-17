"""Tests for CLI sandbox picker presets (aligned with web UI)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.sandbox_presets import (
    CPU_PRESETS,
    GPU_PRESETS,
    apply_sandbox_pick,
    current_sandbox_pick_index,
    sandbox_pick_options,
)


def test_pick_options_include_local_and_ui_presets():
    options = sandbox_pick_options()
    assert options[0].kind == "builtin"
    assert options[0].label == "Local Sandbox"
    cpu_opts = [o for o in options if o.kind == "modal_cpu"]
    gpu_opts = [o for o in options if o.kind == "modal_gpu"]
    assert len(cpu_opts) == len(CPU_PRESETS)
    assert len(gpu_opts) == len(GPU_PRESETS)
    assert any(o.gpu_class == "T4" for o in gpu_opts)


def test_apply_modal_gpu_pick_sets_compute(tmp_path, monkeypatch):
    cfg = MagicMock()
    saved = {}

    def _set(key, value):
        saved[key] = value

    cfg.set.side_effect = _set
    cfg.save = MagicMock()
    cfg.get.side_effect = lambda key, default=None: saved.get(key, default)

    option = next(o for o in sandbox_pick_options() if o.gpu_class == "T4")
    with patch(
        "agent.sandbox_presets.set_sandbox_backend",
        return_value="modal",
    ) as set_backend:
        label = apply_sandbox_pick(option, cfg)
    assert label == "Modal Sandbox"
    set_backend.assert_called_once_with("modal", cfg)
    assert saved["sandbox.compute_type"] == "gpu"
    assert saved["sandbox.gpu_class"] == "T4"
    assert saved["sandbox.cpu_cores"] == 8.0
    assert saved["sandbox.ram_gb"] == 32.0
    cfg.save.assert_called_once()


def test_current_index_matches_gpu_preset():
    cfg = MagicMock()

    def _get(key, default=None):
        return {
            "agent.cli_sandbox": "modal",
            "sandbox.compute_type": "gpu",
            "sandbox.gpu_class": "A100",
            "sandbox.cpu_cores": 16.0,
            "sandbox.ram_gb": 64.0,
        }.get(key, default)

    cfg.get.side_effect = _get
    options = sandbox_pick_options()
    idx = current_sandbox_pick_index(cfg, options)
    assert idx is not None
    assert options[idx].gpu_class == "A100"
