"""Llama macOS app bridge: probe, open, and install the CLI."""

from __future__ import annotations

import subprocess
from pathlib import Path

from agent_server import llama_runtime as bridge

import pytest


@pytest.fixture(autouse=True)
def _reset_llama_runtime_state():
    """Workers share this module. A leftover install phase hides a live server."""
    bridge._set("idle")
    bridge._load_jobs.clear()
    bridge._install_job = None
    yield
    bridge._set("idle")
    bridge._load_jobs.clear()
    bridge._install_job = None


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


def test_wait_until_serving_starts_llama_then_waits(monkeypatch):
    calls = {"n": 0}

    def fake_status():
        calls["n"] += 1
        return {"running": calls["n"] > 1}

    started: list[bool] = []
    monkeypatch.setattr(bridge, "status", fake_status)
    monkeypatch.setattr(bridge, "llama_binary", lambda: "/tmp/llama")
    monkeypatch.setattr(bridge, "ensure", lambda: started.append(True))
    monkeypatch.setattr(bridge.time, "sleep", lambda _seconds: None)
    assert bridge.wait_until_serving(timeout=5) is True
    assert started == [True]


def test_status_keeps_download_progress_while_the_server_is_up(monkeypatch):
    class _Response:
        status_code = 200

        def json(self):
            return {"data": [{"id": "org/model:Q4"}]}

    monkeypatch.setattr(bridge.httpx, "get", lambda *args, **kwargs: _Response())
    bridge._set("installing", "Downloading 40%")
    snapshot = bridge.status()
    assert snapshot["running"] is True
    assert snapshot["phase"] == "installing"
    assert snapshot["detail"] == "Downloading 40%"
    bridge._set("ready", "")


def test_download_streams_cli_lines_into_the_log(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.diagnostics.logging_setup.LOGS_DIR", tmp_path)

    class _Stdout:
        def __init__(self, text: str):
            self._text = text
            self._index = 0

        def read(self, count: int) -> str:
            chunk = self._text[self._index : self._index + count]
            self._index += count
            return chunk

    class _Proc:
        def __init__(self, *_args, **_kwargs):
            self.stdout = _Stdout("Fetching 10%\rFetching 100%\n")
            self.returncode = 0

        def wait(self):
            return 0

    real_popen = subprocess.Popen

    def _popen(cmd, **kwargs):
        if "download" in cmd:
            return _Proc()
        return real_popen(cmd, **kwargs)

    monkeypatch.setattr(bridge.subprocess, "Popen", _popen)
    monkeypatch.setattr(bridge, "list_models", lambda: [])
    bridge._download("/tmp/llama", "org/gemma")
    snapshot = bridge.status()
    assert snapshot["phase"] == "ready"
    assert "Fetching 100%" in snapshot["log"]
    assert "Fetching 100%" in (tmp_path / "llama.log").read_text(encoding="utf-8")
    assert "Fetching 100%" in (tmp_path / "cli.log").read_text(encoding="utf-8")


def test_remove_deletes_the_huggingface_cache_folder(monkeypatch, tmp_path):
    repo = tmp_path / ".cache" / "huggingface" / "hub" / "models--ggml-org--gemma"
    snapshot = repo / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    (snapshot / "model-Q4_0.gguf").write_bytes(b"weights")
    monkeypatch.setattr(bridge.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(bridge, "unload_model", lambda _model_id: {"ok": True})

    result = bridge.remove_model("ggml-org/gemma:Q4_0")

    assert result["ok"] is True
    assert not repo.exists()


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


def test_weights_label_and_installed_row_states(tmp_path, monkeypatch):
    missing = tmp_path / "gone.gguf"
    assert bridge._weights_label(None) is None
    assert bridge._weights_label(str(missing)) is None
    assert bridge._arg(["--ctx-size"], "--ctx-size") is None
    assert bridge._arg([], "--model") is None

    small = tmp_path / "a.gguf"
    other = tmp_path / "b.gguf"
    small.write_bytes(b"x")
    sizes = {small: 2_000_000}
    real_stat = Path.stat

    class _Size:
        def __init__(self, nbytes: int):
            self.st_size = nbytes

    def sized_stat(self, *args, **kwargs):
        if self in sizes:
            return _Size(sizes[self])
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", sized_stat)
    assert bridge._weights_label(str(small)) == "2 MB"
    other.write_bytes(b"y")
    sizes[small] = 500_000_000
    sizes[other] = 500_000_000
    assert bridge._weights_label(str(small)) == "1 GB"

    bridge._load_jobs["org/loading:Q4"] = "loading"
    bridge._load_jobs["org/failed:Q4"] = "disk full"
    rows = bridge._installed_rows(
        [
            {"id": "  "},
            {
                "id": "org/loading:Q4",
                "status": {"value": "unloaded", "args": ["--ctx-size", "4096", "--model"]},
                "architecture": {"input_modalities": ["image", "text"]},
            },
            {
                "id": "org/failed:Q4",
                "status": {"value": "ready", "args": ["--ctx-size", "nope"]},
            },
        ]
    )
    by_id = {row["id"]: row for row in rows}
    assert by_id["org/loading:Q4"]["state"] == "loading"
    assert by_id["org/loading:Q4"]["vision"] is True
    assert by_id["org/loading:Q4"]["context"] == 4096
    assert by_id["org/failed:Q4"]["state"] == "failed"
    assert by_id["org/failed:Q4"]["error"] == "disk full"
    assert by_id["org/failed:Q4"]["context"] is None
    bridge._load_jobs.pop("org/loading:Q4", None)
    bridge._load_jobs.pop("org/failed:Q4", None)


def test_wait_until_serving_does_nothing_without_a_binary(monkeypatch):
    monkeypatch.setattr(bridge, "status", lambda: {"running": False})
    monkeypatch.setattr(bridge, "llama_binary", lambda: None)
    assert bridge.wait_until_serving() is False


def test_ensure_does_not_install_twice(monkeypatch):
    monkeypatch.setattr(bridge, "list_models", lambda: None)
    monkeypatch.setattr(bridge, "app_installed", lambda: False)
    monkeypatch.setattr(bridge, "llama_binary", lambda: None)
    monkeypatch.setattr(bridge, "_install_cli_then_serve", lambda: None)
    bridge._set("installing", "Installing Llama with Homebrew…")
    snapshot = bridge.ensure()
    assert snapshot["phase"] == "installing"
