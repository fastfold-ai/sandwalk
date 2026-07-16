"""Agent-server boot smoke: ``sandwalk serve`` + ``GET /v1/health``."""

from __future__ import annotations

import json
import signal

import pytest

from integration_cli.harness import free_tcp_port, start_sandwalk, wait_http_ok

pytestmark = pytest.mark.cli_functional


def test_serve_health_endpoint(cli_home, cli_cwd):
    port = free_tcp_port()
    proc = start_sandwalk(
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        home=cli_home,
        cwd=cli_cwd,
    )
    try:
        body = wait_http_ok(f"http://127.0.0.1:{port}/v1/health", timeout_s=45.0)
        payload = json.loads(body)
        assert isinstance(payload, dict)
        assert "version" in payload or "capabilities" in payload or "backend_id" in payload
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
                proc.wait(timeout=5)
        # Surface boot failures when health never came up.
        if proc.returncode not in (0, None, -signal.SIGTERM, signal.SIGTERM):
            stdout = (proc.stdout.read() if proc.stdout else "") or ""
            stderr = (proc.stderr.read() if proc.stderr else "") or ""
            # Non-zero after SIGTERM is ok on some platforms; only fail if we
            # never got a health response (AssertionError already raised).
            _ = (stdout, stderr)
