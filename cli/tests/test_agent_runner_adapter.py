"""The session adapter that starts AgentRunner, including the Llama wake-up."""

from __future__ import annotations

from types import SimpleNamespace

from agent_server.service import agent_runner


class _Config:
    def __init__(self):
        self._data = {}
        self._dirty_keys = set()
        self.profile = {"backend": "openai"}
        self.fail_set = False
        self.fail_get = False

    def set_openai_active_profile(self, profile_id):
        if self.fail_set:
            raise RuntimeError("no profile")
        self.profile = {"backend": "llama" if profile_id == "llama_local" else "openai"}

    def get_openai_profile(self):
        if self.fail_get:
            raise RuntimeError("unreadable")
        return self.profile

    def set(self, key, value):
        self._data[key] = value


class _Message:
    def __init__(self, role, content):
        self.role = role
        self.content = content


def test_run_existing_agent_wires_context(tmp_path, monkeypatch):
    cfg = _Config()
    seen = {}
    ready = []
    done = []

    class _Session:
        def __init__(self, **kwargs):
            seen["session"] = kwargs

    class _Trajectory:
        def __init__(self, session_id=None):
            self.session_id = session_id
            self.turns = []

        def add_turn(self, user, assistant):
            self.turns.append((user, assistant))

    class _Runner:
        def __init__(self, session, trajectory=None, headless=False):
            seen["trajectory"] = trajectory

        def run(self, content, context, progress_callback=None):
            seen["content"] = content
            seen["context"] = context
            progress_callback("tick")
            return SimpleNamespace(summary="")

    monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
    monkeypatch.setattr("agent.session.Session", _Session)
    monkeypatch.setattr("agent.trajectory.Trajectory", _Trajectory)
    monkeypatch.setattr("agent.runner.AgentRunner", _Runner)
    monkeypatch.setattr(
        "agent_server.session_sandbox_service.effective_session_sandbox_backend",
        lambda backend, config=None: backend or "builtin",
    )
    monkeypatch.setattr("agent_server.llama_runtime.wait_until_serving", lambda timeout=20: seen.setdefault("woke", True))

    workspace = tmp_path / "chat"
    summary = agent_runner.run_existing_agent(
        "next",
        str(workspace),
        lambda event: seen.setdefault("progress", event),
        [
            _Message("user", "hi"),
            _Message("assistant", "hello"),
            _Message("user", "dangling"),
        ],
        [{"name": "mcp"}],
        project_context="proj",
        specialist_instructions="be brief",
        allowed_skill_names=["fold"],
        session_id="sess-1",
        sandbox_backend="modal",
        allowed_tool_names=["read"],
        on_runner_ready=ready.append,
        on_runner_done=lambda: done.append("done"),
        provider="openai",
        model="gpt-test",
        openai_profile_id="llama_local",
        capy_mode=True,
    )
    assert summary == "Done."
    assert seen["woke"] is True
    assert seen["context"]["capy_mode"] is True
    assert seen["context"]["mcp_servers"] == []
    assert seen["context"]["sandbox_backend"] == "modal"
    assert (workspace / "outputs").is_dir()
    assert seen["trajectory"].turns == [("hi", "hello")]
    assert ready and done == [None] or done
    assert cfg._dirty_keys == set()
    assert cfg._data["llm.model"] == "gpt-test"


def test_run_existing_agent_skips_optional_context(monkeypatch):
    cfg = _Config()
    cfg.fail_set = True
    cfg.fail_get = True
    captured = {}

    class _Runner:
        def __init__(self, *args, **kwargs):
            return None

        def run(self, content, context, progress_callback=None):
            captured["context"] = context
            return SimpleNamespace(summary="ok")

    monkeypatch.setattr("agent.config.Config.load", lambda: cfg)
    monkeypatch.setattr("agent.session.Session", lambda **kwargs: object())
    monkeypatch.setattr("agent.trajectory.Trajectory", lambda **kwargs: SimpleNamespace(add_turn=lambda *a: None))
    monkeypatch.setattr("agent.runner.AgentRunner", _Runner)
    monkeypatch.setattr(
        "agent_server.session_sandbox_service.effective_session_sandbox_backend",
        lambda backend, config=None: "builtin",
    )
    summary = agent_runner.run_existing_agent(
        "ping",
        None,
        None,
        [],
        None,
        openai_profile_id="missing",
    )
    assert summary == "ok"
    assert captured["context"] == {"sandbox_backend": "builtin"}
