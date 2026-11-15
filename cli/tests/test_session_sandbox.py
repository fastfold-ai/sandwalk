"""Tests for per-session sandbox backend overrides."""

from __future__ import annotations

from pathlib import Path

from agent_server.session_sandbox_service import (
    SessionSandboxService,
    effective_session_sandbox_backend,
)
from agent_server.store import AgentStore


class _Cfg:
    def __init__(self, backend: str = "builtin") -> None:
        self._backend = backend

    def get(self, key, default=None):
        if key == "sandbox.backend":
            return self._backend
        return default


def test_effective_session_sandbox_backend_override():
    assert effective_session_sandbox_backend("modal", config=_Cfg("builtin")) == "modal"
    assert effective_session_sandbox_backend("builtin", config=_Cfg("modal")) == "builtin"
    # Unset session backend always defaults to Built-in (never inherits global Modal).
    assert effective_session_sandbox_backend(None, config=_Cfg("modal")) == "builtin"
    assert effective_session_sandbox_backend(None, config=_Cfg("builtin")) == "builtin"


def test_store_persists_session_sandbox_backend(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    session = store.create_session(title="t", workspace_path=None, sandbox_backend="modal")
    assert session.sandbox_backend == "modal"
    updated = store.update_session(
        session.id,
        sandbox_backend="builtin",
        update_sandbox_backend=True,
    )
    assert updated is not None
    assert updated.sandbox_backend == "builtin"
    cleared = store.update_session(
        session.id,
        sandbox_backend=None,
        update_sandbox_backend=True,
    )
    assert cleared is not None
    assert cleared.sandbox_backend is None


def test_session_sandbox_status_ignores_global_modal(tmp_path: Path, monkeypatch):
    store = AgentStore(tmp_path / "agent.db")
    session = store.create_session(title="t", workspace_path=str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir(parents=True, exist_ok=True)

    class _Settings:
        backend = "modal"
        modal_configured = True
        compute_type = "cpu"
        gpu_class = "T4"
        cpu_cores = 2.0
        ram_gb = 8.0
        cpu_image = "debian_slim"

    monkeypatch.setattr(
        "agent_server.session_sandbox_service.SandboxSettingsService.get",
        staticmethod(lambda: _Settings()),
    )
    status = SessionSandboxService(store).status(session.id)
    assert status.session_backend is None
    assert status.global_backend == "modal"
    assert status.backend == "builtin"
    assert status.status == "ready"


class _ModalSettings:
    backend = "builtin"
    modal_configured = True
    compute_type = "gpu"
    gpu_class = "T4"
    cpu_cores = 4.0
    ram_gb = 16.0
    cpu_image = "python:3.12-slim"
    gpu_image = "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"


class _FakeModalSandbox:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.polls = 0

    def poll(self):
        self.polls += 1
        if self.error is not None:
            raise self.error
        return self.result


def _modal_session(tmp_path: Path, monkeypatch, sandbox: _FakeModalSandbox):
    from agent.sandbox_backend.handle import (
        SandboxHandle,
        clear_active_handles,
        register_handle,
    )

    clear_active_handles()
    store = AgentStore(tmp_path / "agent.db")
    session = store.create_session(
        title="t", workspace_path=str(tmp_path / "ws"), sandbox_backend="modal"
    )
    monkeypatch.setattr(
        "agent_server.session_sandbox_service.SandboxSettingsService.get",
        staticmethod(lambda: _ModalSettings()),
    )
    handle = SandboxHandle(
        kind="modal",
        backend=object(),
        workspace_root=str(tmp_path / "ws"),
        skills_sources=[],
        session_id=session.id,
        provider_sandbox_name="sandwalk-test",
        modal_sandbox=sandbox,
        started_at=1_700_000_000.0,
    )
    register_handle(handle)
    return store, session, handle


def test_running_modal_sandbox_reports_when_it_started(tmp_path: Path, monkeypatch):
    from agent.sandbox_backend.handle import clear_active_handles

    sandbox = _FakeModalSandbox(result=None)
    store, session, _handle = _modal_session(tmp_path, monkeypatch, sandbox)
    try:
        service = SessionSandboxService(store)
        first = service.status(session.id)
        second = service.status(session.id)
    finally:
        clear_active_handles()
    assert first.status == "running"
    assert first.provider_sandbox_name == "sandwalk-test"
    assert first.started_at is not None
    assert first.started_at.timestamp() == 1_700_000_000.0
    # Reopening the chat asks again and gets the same start time.
    assert second.started_at == first.started_at
    # Modal is asked once, then the answer is reused for a few seconds.
    assert sandbox.polls == 1
    assert first.model_dump(by_alias=True, mode="json")["startedAt"].startswith(
        "2023-11-14T22:13:20"
    )


def test_modal_sandbox_that_modal_ended_is_reported_stopped(tmp_path: Path, monkeypatch):
    from agent.sandbox_backend.handle import clear_active_handles, get_active_handle

    sandbox = _FakeModalSandbox(result=137)
    store, session, _handle = _modal_session(tmp_path, monkeypatch, sandbox)
    try:
        status = SessionSandboxService(store).status(session.id)
        handle_after = get_active_handle(session.id)
    finally:
        clear_active_handles()
    assert status.status == "stopped"
    assert status.started_at is None
    assert status.provider_sandbox_name is None
    # No known deadline passed, so the cause is not guessed.
    assert status.stop_reason == "ended"
    assert status.stopped_at is not None
    assert status.detail == "This sandbox ended on its own."
    assert handle_after is None


def test_modal_not_found_counts_as_stopped(tmp_path: Path, monkeypatch):
    from agent.sandbox_backend.handle import clear_active_handles

    class NotFoundError(Exception):
        pass

    sandbox = _FakeModalSandbox(error=NotFoundError("Sandbox not found"))
    store, session, _handle = _modal_session(tmp_path, monkeypatch, sandbox)
    try:
        status = SessionSandboxService(store).status(session.id)
    finally:
        clear_active_handles()
    assert status.status == "stopped"


def test_unreachable_modal_keeps_the_sandbox_running(tmp_path: Path, monkeypatch):
    from agent.sandbox_backend.handle import clear_active_handles, get_active_handle

    sandbox = _FakeModalSandbox(error=OSError("network down"))
    store, session, _handle = _modal_session(tmp_path, monkeypatch, sandbox)
    try:
        status = SessionSandboxService(store).status(session.id)
        handle_after = get_active_handle(session.id)
    finally:
        clear_active_handles()
    assert status.status == "running"
    assert handle_after is not None


def _lifecycle_extras(*, idle: int = 600, limit: int = 1800, created_here: bool = True):
    from agent.sandbox_backend.activity import SandboxActivity

    return {
        "idle_timeout_seconds": idle,
        "max_lifetime_seconds": limit,
        "created_here": created_here,
        "activity": SandboxActivity(),
    }


def test_running_sandbox_reports_its_lifetime_rules(tmp_path: Path, monkeypatch):
    import time

    from agent.sandbox_backend.handle import clear_active_handles

    sandbox = _FakeModalSandbox(result=None)
    store, session, handle = _modal_session(tmp_path, monkeypatch, sandbox)
    now = time.time()
    handle.started_at = now - 120
    handle.extras.update(_lifecycle_extras())
    handle.extras["activity"].last_active_at = now - 45
    try:
        status = SessionSandboxService(store).status(session.id)
    finally:
        clear_active_handles()
    assert status.status == "running"
    assert status.idle_timeout_seconds == 600
    assert status.max_lifetime_seconds == 1800
    assert status.busy is False
    assert status.last_active_at is not None
    assert abs(status.last_active_at.timestamp() - (now - 45)) < 1
    assert status.expires_at is not None
    assert abs(status.expires_at.timestamp() - (now - 120 + 1800)) < 1
    dumped = status.model_dump(by_alias=True, mode="json")
    assert dumped["idleTimeoutSeconds"] == 600
    assert dumped["expiresAt"] and dumped["lastActiveAt"]


def test_reattached_sandbox_has_no_hard_stop_time(tmp_path: Path, monkeypatch):
    from agent.sandbox_backend.handle import clear_active_handles

    sandbox = _FakeModalSandbox(result=None)
    store, session, handle = _modal_session(tmp_path, monkeypatch, sandbox)
    handle.extras.update(_lifecycle_extras(created_here=False))
    try:
        status = SessionSandboxService(store).status(session.id)
    finally:
        clear_active_handles()
    assert status.max_lifetime_seconds == 1800
    assert status.expires_at is None


def test_command_in_flight_marks_the_sandbox_busy(tmp_path: Path, monkeypatch):
    from agent.sandbox_backend.handle import clear_active_handles

    sandbox = _FakeModalSandbox(result=None)
    store, session, handle = _modal_session(tmp_path, monkeypatch, sandbox)
    handle.extras.update(_lifecycle_extras())
    try:
        with handle.extras["activity"].track():
            busy = SessionSandboxService(store).status(session.id).busy
        handle.extras.pop("liveness_checked_at")
        idle = SessionSandboxService(store).status(session.id).busy
    finally:
        clear_active_handles()
    assert busy is True
    assert idle is False


def test_idle_stop_is_dated_from_the_last_command(tmp_path: Path, monkeypatch):
    """Opening the chat an hour later must not say "stopped just now"."""
    import time

    from agent.sandbox_backend.handle import clear_active_handles

    sandbox = _FakeModalSandbox(result=124)
    store, session, handle = _modal_session(tmp_path, monkeypatch, sandbox)
    now = time.time()
    handle.started_at = now - 4000
    handle.extras.update(_lifecycle_extras(idle=600, limit=7200))
    handle.extras["activity"].last_active_at = now - 3600
    try:
        service = SessionSandboxService(store)
        status = service.status(session.id)
        again = service.status(session.id)
    finally:
        clear_active_handles()
    assert status.status == "stopped"
    assert status.stop_reason == "idle"
    assert status.stopped_at is not None
    assert abs(status.stopped_at.timestamp() - (now - 3000)) < 1
    assert status.detail == "Modal stopped this sandbox after 10 min without activity."
    assert status.idle_timeout_seconds == 600
    # The note survives later reads, after the handle is gone.
    assert again.stop_reason == "idle"
    assert again.stopped_at == status.stopped_at


def test_time_limit_stop_is_named(tmp_path: Path, monkeypatch):
    import time

    from agent.sandbox_backend.handle import clear_active_handles

    sandbox = _FakeModalSandbox(result=124)
    store, session, handle = _modal_session(tmp_path, monkeypatch, sandbox)
    now = time.time()
    handle.started_at = now - 1810
    handle.extras.update(_lifecycle_extras(idle=600, limit=1800))
    handle.extras["activity"].last_active_at = now - 20
    try:
        status = SessionSandboxService(store).status(session.id)
    finally:
        clear_active_handles()
    assert status.stop_reason == "time_limit"
    assert status.detail == "This sandbox reached its 30 min time limit."
    assert abs(status.stopped_at.timestamp() - (now - 10)) < 1


def test_user_stop_and_restart_clear_the_stop_note(tmp_path: Path, monkeypatch):
    from agent.sandbox_backend.handle import (
        SandboxHandle,
        clear_active_handles,
        get_last_stop,
        register_handle,
    )

    sandbox = _FakeModalSandbox(result=137)
    store, session, _handle = _modal_session(tmp_path, monkeypatch, sandbox)
    try:
        service = SessionSandboxService(store)
        assert service.status(session.id).stop_reason == "ended"
        assert get_last_stop(session.id) is not None
        # Starting a new sandbox drops the note about the old one.
        register_handle(
            SandboxHandle(
                kind="modal",
                backend=object(),
                workspace_root=str(tmp_path / "ws"),
                skills_sources=[],
                session_id=session.id,
                modal_sandbox=_FakeModalSandbox(result=None),
            )
        )
        assert get_last_stop(session.id) is None
        assert service.status(session.id).status == "running"
        # A user Stop leaves nothing to explain.
        monkeypatch.setattr(
            "agent.sandbox_backend.handle._run_modal_blocking", lambda fn: None
        )
        stopped = service.stop(session.id)
    finally:
        clear_active_handles()
    assert stopped.status == "stopped"
    assert stopped.stop_reason is None
    assert stopped.stopped_at is None


def test_commands_through_the_backend_count_as_activity():
    import time
    from types import SimpleNamespace

    from agent.sandbox_backend.activity import SandboxActivity
    from agent.sandbox_backend.lifecycle import _wrap_modal_backend_for_async

    activity = SandboxActivity()
    activity.last_active_at = time.time() - 500
    seen = {}

    def original_execute(command, *, timeout=None):
        seen["busy_during"] = activity.busy
        return "ok"

    backend = SimpleNamespace(execute=original_execute)
    _wrap_modal_backend_for_async(backend, SimpleNamespace(), activity)
    assert backend.execute("ls") == "ok"
    assert seen["busy_during"] is True
    assert activity.busy is False
    assert time.time() - activity.last_active_at < 2


class _LimitsConfig:
    def __init__(self, **values) -> None:
        self._values = values

    def get(self, key, default=None):
        return self._values.get(key, default)


def test_time_limit_defaults_to_the_old_thirty_minutes():
    from agent.sandbox_backend.profile import (
        sandbox_idle_timeout_seconds,
        sandbox_max_lifetime_seconds,
    )

    cfg = _LimitsConfig(**{"sandbox.timeout": 30, "sandbox.idle_ttl_seconds": 600})
    assert sandbox_idle_timeout_seconds(cfg) == 600
    assert sandbox_max_lifetime_seconds(cfg) == 1800
    # Nothing set at all still gives the same numbers.
    assert sandbox_max_lifetime_seconds(_LimitsConfig()) == 1800


def test_time_limit_setting_wins_and_is_capped_at_modals_24_hours():
    from agent.sandbox_backend.profile import sandbox_max_lifetime_seconds

    assert (
        sandbox_max_lifetime_seconds(
            _LimitsConfig(**{"sandbox.max_lifetime_seconds": 4 * 3600})
        )
        == 4 * 3600
    )
    assert (
        sandbox_max_lifetime_seconds(
            _LimitsConfig(**{"sandbox.max_lifetime_seconds": 72 * 3600})
        )
        == 24 * 3600
    )


def test_time_limit_stays_longer_than_the_idle_timeout():
    from agent.sandbox_backend.profile import sandbox_max_lifetime_seconds

    cfg = _LimitsConfig(
        **{"sandbox.max_lifetime_seconds": 600, "sandbox.idle_ttl_seconds": 3600}
    )
    assert sandbox_max_lifetime_seconds(cfg) == 3660


def test_sandbox_settings_save_and_report_the_time_limit(tmp_path: Path, monkeypatch):
    from agent.config import Config
    from agent_server.models import UpdateSandboxSettingsRequest
    from agent_server.sandbox_settings_service import SandboxSettingsService

    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    assert SandboxSettingsService.get().max_lifetime_seconds == 1800
    updated = SandboxSettingsService.update(
        UpdateSandboxSettingsRequest(max_lifetime_seconds=8 * 3600, idle_ttl_seconds=1800)
    )
    assert updated.max_lifetime_seconds == 8 * 3600
    assert updated.idle_ttl_seconds == 1800
    assert SandboxSettingsService.get().max_lifetime_seconds == 8 * 3600
    # Past Modal's ceiling is clamped, not rejected.
    capped = SandboxSettingsService.update(
        UpdateSandboxSettingsRequest(max_lifetime_seconds=100 * 3600)
    )
    assert capped.max_lifetime_seconds == 24 * 3600


def test_status_reports_the_limits_the_next_sandbox_will_get(tmp_path: Path, monkeypatch):
    from agent.sandbox_backend.handle import clear_active_handles

    class _Settings(_ModalSettings):
        idle_ttl_seconds = 1800
        max_lifetime_seconds = 4 * 3600

    sandbox = _FakeModalSandbox(result=None)
    store, session, handle = _modal_session(tmp_path, monkeypatch, sandbox)
    monkeypatch.setattr(
        "agent_server.session_sandbox_service.SandboxSettingsService.get",
        staticmethod(lambda: _Settings()),
    )
    handle.extras.update(_lifecycle_extras(idle=600, limit=1800))
    try:
        status = SessionSandboxService(store).status(session.id)
    finally:
        clear_active_handles()
    # The running sandbox keeps the limits it was created with.
    assert status.idle_timeout_seconds == 600
    assert status.max_lifetime_seconds == 1800
    assert status.configured_idle_timeout_seconds == 1800
    assert status.configured_max_lifetime_seconds == 4 * 3600
