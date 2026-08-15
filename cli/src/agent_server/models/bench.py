"""API models for /v1/bench/*."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from agent_server.models.base import ApiModel


class BenchSuiteCard(ApiModel):
    id: str
    title: str
    description: str = ""
    lane: Literal["intelligence", "skills"] = "intelligence"
    runner: Literal["completion", "agent"] = "agent"
    pack_id: str | None = None
    matrix: str | None = None
    question_count: int = 0
    sample_sizes: list[int] = Field(default_factory=list)
    default_sample_size: int | None = None
    available: bool = True
    unavailable_reason: str | None = None
    author: str | None = None
    author_avatar: str | None = None
    code_exec: bool = False
    installable: bool = False
    requires_hf_token: bool = False
    hf_token_configured: bool = False
    installing: bool = False
    install_error: str | None = None
    """Human progress while installing, e.g. ``file 2/6 · 12.4 MB``."""
    install_progress: str | None = None
    install_bytes_done: int | None = None
    install_bytes_total: int | None = None
    """True when a downloadable dataset is cached on disk (Remove is available)."""
    installed: bool = False
    """Bytes this suite occupies in the local bench cache."""
    installed_bytes: int | None = None
    """Questions actually cached locally (may differ from the declared corpus)."""
    installed_count: int | None = None
    """Set when the fast parquet download needs a reader that is not installed."""
    missing_dependency: str | None = None
    required_skills: list[str] = Field(default_factory=list)
    required_mcps: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    missing_mcps: list[str] = Field(default_factory=list)


class BenchSuiteList(ApiModel):
    data: list[BenchSuiteCard]
    """Total bytes used by every cached bench dataset."""
    cache_bytes: int = 0
    cache_path: str | None = None


class BenchUninstallResponse(ApiModel):
    ok: bool
    suite_id: str
    summary: str = ""
    freed_bytes: int = 0
    removed: list[str] = Field(default_factory=list)


class BenchInstallResponse(ApiModel):
    ok: bool
    suite_id: str
    path: str | None = None
    summary: str = ""
    needs_hf_token: bool = False
    status: Literal["installing", "done", "error"] = "done"


class BenchSuiteRef(ApiModel):
    suite_id: str
    sample_size: int | None = None


class BenchSpawnRequest(ApiModel):
    suites: list[BenchSuiteRef]
    model: str | None = None
    models: list[str] = Field(default_factory=list)
    provider: str | None = None
    project_name: str | None = None
    specialist_id: str | None = None
    thinking: bool = False
    dry_run: bool = False
    # Parallel cells within a single suite run (in-process workers).
    concurrency: int = 1
    # Independent stacks that may run at the same time (distinct from concurrency).
    parallel_runs: int | None = None
    # After a successful suite, optionally delete the bench project + sessions.
    cleanup_sessions: bool | None = False
    # Dashboard Bench defaults to ui; `sandwalk eval` should send cli.
    client_surface: Literal["cli", "ui"] = "ui"


class BenchSpawnResponse(ApiModel):
    run_ids: list[str]
    queued: int


class BenchProgress(ApiModel):
    type: str = "progress"
    phase: str = ""
    model_id: str = ""
    benchmark: str = ""
    message: str = ""
    current: int = 0
    total: int = 0
    bench_current: int = 0
    bench_total: int = 0
    in_flight: int = 0
    run_id: str | None = None


class BenchQueueItem(ApiModel):
    run_id: str
    model_id: str
    suites: list[str] = Field(default_factory=list)
    sample_sizes: list[int | None] = Field(default_factory=list)
    status: Literal["queued", "running", "paused"] = "queued"
    last_progress: BenchProgress | None = None
    provider: str | None = None
    """When this running segment began (unset while queued/paused)."""
    started_at: str | None = None
    """Active seconds before ``started_at`` (running) or frozen total (paused)."""
    elapsed_s: float = 0


class BenchActiveStatus(ApiModel):
    running: bool = False
    phase: str = "idle"
    current_model: str | None = None
    current_run_id: str | None = None
    last_progress: BenchProgress | None = None
    queue: list[BenchQueueItem] = Field(default_factory=list)
    inflight: list[BenchQueueItem] = Field(default_factory=list)
    paused: list[BenchQueueItem] = Field(default_factory=list)
    parallel_runs: int = 1
    resumable_run_id: str | None = None
    project_id: str | None = None


class BenchResultSummary(ApiModel):
    run_id: str
    model_id: str
    benchmark: str
    accuracy: float
    correct: int
    total: int
    time_s: float
    thinking_used: bool = False
    project_id: str | None = None
    created_at: str | None = None
    status: str | None = None
    reasoning_effort: str | None = None
    reasoning_fast: bool | None = None
    name: str | None = None
    provider: str | None = None
    lifetime_tokens: int | None = None


class BenchResultList(ApiModel):
    data: list[BenchResultSummary]
    next_cursor: str | None = None
    total: int = 0
    providers: list[str] = []


class BenchRunPatchRequest(ApiModel):
    name: str | None = None


class BenchCancelResponse(ApiModel):
    ok: bool
    run_id: str | None = None


class BenchPauseResponse(ApiModel):
    ok: bool
    run_id: str | None = None


class BenchResumeResponse(ApiModel):
    ok: bool
    run_id: str | None = None


class BenchResetResponse(ApiModel):
    ok: bool
    cleared: int
    sessions_deleted: int = 0


class BenchGradeRequest(ApiModel):
    run_id: str | None = None
    session_id: str | None = None


class BenchGradeResponse(ApiModel):
    ok: bool
    detail: str = ""
    result: dict[str, Any] | None = None
