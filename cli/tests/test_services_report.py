"""Settings → Logs daemon snapshot."""

from __future__ import annotations

import os

from agent_server import services_report as report


def test_services_report_lists_the_api_and_a_stopped_llama(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "LOGS_DIR", tmp_path)
    monkeypatch.setattr(report, "_process_stats", lambda pid: (4096, 1.5, "sandwalk serve"))
    monkeypatch.setattr(report, "_sandwalk_port", lambda pid: 8787)
    monkeypatch.setattr(report, "_pid_on_port", lambda port: None)
    monkeypatch.setattr("agent_server.llama_runtime.serve_pid", lambda: None)
    monkeypatch.setattr("agent_server.llama_runtime.llama_binary", lambda: None)

    snapshot = report.build_services_report(version="0.1.8")

    api = snapshot.processes[0]
    llama = snapshot.processes[1]
    assert api.id == "sandwalk"
    assert api.pid == os.getpid()
    assert api.port == 8787
    assert api.rss_bytes == 4096
    assert api.status == "running"
    assert llama.id == "llama"
    assert llama.status == "stopped"
    assert llama.port == 9931
    assert llama.pid is None
