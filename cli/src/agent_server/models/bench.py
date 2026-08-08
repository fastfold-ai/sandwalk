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
    required_skills: list[str] = Field(default_factory=list)
    required_mcps: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    missing_mcps: list[str] = Field(default_factory=list)


class BenchSuiteList(ApiModel):
    data: list[BenchSuiteCard]


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


class BenchQueueItem(ApiModel):
    run_id: str
    model_id: str
    suites: list[str] = Field(default_factory=list)


class BenchActiveStatus(ApiModel):
    running: bool = False
    phase: str = "idle"
    current_model: str | None = None
    current_run_id: str | None = None
    last_progress: BenchProgress | None = None
    queue: list[BenchQueueItem] = Field(default_factory=list)


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


class BenchResultList(ApiModel):
    data: list[BenchResultSummary]


class BenchCancelResponse(ApiModel):
    ok: bool
    run_id: str | None = None


class BenchResetResponse(ApiModel):
    ok: bool
    cleared: int


class BenchGradeRequest(ApiModel):
    run_id: str | None = None
    session_id: str | None = None


class BenchGradeResponse(ApiModel):
    ok: bool
    detail: str = ""
    result: dict[str, Any] | None = None
