"""Tests for the agent-server startup banner."""

from io import StringIO
from pathlib import Path

from rich.console import Console

from _version import __version__
from agent_server.banner import print_server_banner


def _capture(**kwargs) -> str:
    stream = StringIO()
    console = Console(
        file=stream,
        force_terminal=False,
        color_system=None,
        width=240,
    )
    print_server_banner(console=console, **kwargs)
    return stream.getvalue()


def test_server_banner_shows_local_connection_details():
    output = _capture(
        host="127.0.0.1",
        port=8787,
        public=False,
        auth_enabled=False,
        ui_available=True,
    )

    assert f"sandwalk v{__version__}" in output
    assert "Agent server" in output
    assert "Server  http://127.0.0.1:8787" in output
    assert "Dashboard  http://127.0.0.1:8787" in output
    assert "API docs  http://127.0.0.1:8787/docs" in output
    assert "Local only · no API key" in output
    assert "Press Ctrl+C to stop" in output


def test_server_banner_shows_unix_socket_and_auth(tmp_path: Path):
    socket = tmp_path / "agent.sock"
    output = _capture(
        host="127.0.0.1",
        port=8787,
        public=False,
        auth_enabled=True,
        uds=socket,
    )

    assert f"Socket  {socket}" in output
    assert "Local only · API key required" in output
    assert "API docs" not in output
