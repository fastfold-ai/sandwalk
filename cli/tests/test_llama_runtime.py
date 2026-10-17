"""Llama macOS app bridge: probe, open, and install the CLI."""

from __future__ import annotations

import subprocess
from pathlib import Path

from agent_server import llama_runtime as bridge


def test_status_reports_models_when_the_server_answers(monkeypatch):
    class _Response:
        status_code = 200

        def json(self):
            return {"data": [{"id": "ggml-org/gemma-4-E4B-it-GGUF:Q8_0"}, {"id": ""}]}

    monkeypatch.setattr(bridge.httpx, "get", lambda *args, **kwargs: _Response())
    monkeypatch.setattr(bridge, "app_installed", lambda: True)
    snapshot = bridge.status()
    assert snapshot["running"] is True
    assert snapshot["models"] == ["ggml-org/gemma-4-E4B-it-GGUF:Q8_0"]
    assert snapshot["baseUrl"] == "http://127.0.0.1:9931/v1"
    assert snapshot["phase"] == "ready"


def test_ensure_starts_the_cli_server_when_the_port_is_down(monkeypatch):
    monkeypatch.setattr(bridge, "list_models", lambda: None)
    monkeypatch.setattr(bridge, "llama_binary", lambda: "/tmp/llama")
    started: list[list[str]] = []

    class _Proc:
        def poll(self):
            return None

    def _popen(cmd, **kwargs):
        started.append(cmd)
        return _Proc()

    monkeypatch.setattr(bridge.subprocess, "Popen", _popen)
    bridge._serve_proc = None
    bridge._set("idle")
    snapshot = bridge.ensure()
    assert started == [["/tmp/llama", "serve", "--host", "127.0.0.1", "--port", "9931"]]
    assert snapshot["phase"] == "opening"
    assert snapshot["running"] is False


def test_catalog_keeps_featured_models_that_fit(monkeypatch):
    monkeypatch.setattr(bridge, "list_models", lambda: ["ggml-org/gpt-oss-20b-GGUF:MXFP4"])
    monkeypatch.setattr(bridge, "_models_payload", lambda: None)
    monkeypatch.setattr(bridge, "_memory_bytes", lambda: 64 * 1000**3)

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "brand": "OpenAI",
                    "featured": True,
                    "sizes": [
                        {
                            "name": "GPT-OSS 20B",
                            "builds": [
                                {
                                    "quant": "mxfp4",
                                    "size": "12.1 GB",
                                    "sizeBytes": 12_000_000_000,
                                    "repo": "ggml-org/gpt-oss-20b-GGUF",
                                }
                            ],
                        }
                    ],
                }
            ]

    monkeypatch.setattr(bridge.httpx, "get", lambda *args, **kwargs: _Response())
    snapshot = bridge.catalog()
    assert snapshot["installed"][0]["id"] == "ggml-org/gpt-oss-20b-GGUF:MXFP4"
    assert snapshot["recommended"][0]["installed"] is True
    assert snapshot["recommended"][0]["name"] == "GPT-OSS 20B"


def test_fitp_parse_sums_device_rows():
    output = "MTL0 1481 36 518\nHost 1804 0 57\n"
    assert bridge._parse_fitp(output) == 1481 + 36 + 518 + 1804 + 57
    assert bridge._format_memory(3896) == "3.8 GB"


def test_write_ctx_replaces_an_existing_value(tmp_path):
    path = tmp_path / "models.user.ini"
    bridge._write_ctx(path, "unsloth/gemma-4-E2B-it-GGUF:Q4_K_XL", 4096)
    bridge._write_ctx(path, "unsloth/gemma-4-E2B-it-GGUF:Q4_K_XL", 16384)
    text = path.read_text()
    assert text.count("ctx-size") == 1
    assert "ctx-size = 16384" in text


def test_install_reports_command_and_port_when_the_cli_is_missing(monkeypatch):
    bridge._set("idle")
    bridge._serve_proc = None

    def which(name: str) -> str | None:
        return "/usr/bin/curl" if name == "curl" else None

    def run(cmd, **kwargs):
        if cmd[0] == "/usr/bin/curl":
            Path(cmd[-1]).write_text("echo installed\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "installer finished\n", "")

    monkeypatch.setattr(bridge.shutil, "which", which)
    monkeypatch.setattr(bridge.subprocess, "run", run)
    monkeypatch.setattr(bridge, "llama_binary", lambda: None)
    monkeypatch.setattr(bridge, "list_models", lambda: None)
    bridge._install_cli_then_serve()
    snapshot = bridge.status()
    assert snapshot["phase"] == "error"
    assert snapshot["detail"] == "The llama CLI did not appear after install."
    assert "https://llama.app/install.sh" in snapshot["debug"]["command"]
    assert snapshot["debug"]["port"] == 9931
    assert snapshot["debug"]["exitCode"] == 0
    assert any(path.endswith("/.local/bin/llama") for path in snapshot["debug"]["searched"])
    assert "installer finished" in snapshot["debug"]["log"]


def test_ensure_does_not_install_twice(monkeypatch):
    monkeypatch.setattr(bridge, "list_models", lambda: None)
    monkeypatch.setattr(bridge, "app_installed", lambda: False)
    monkeypatch.setattr(bridge, "llama_binary", lambda: None)
    monkeypatch.setattr(bridge, "_install_cli_then_serve", lambda: None)
    bridge._set("installing", "Installing Llama with Homebrew…")
    snapshot = bridge.ensure()
    assert snapshot["phase"] == "installing"
