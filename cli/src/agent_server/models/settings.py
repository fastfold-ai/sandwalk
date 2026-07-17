from __future__ import annotations

from pydantic import Field

from agent_server.models.base import ApiModel


class RuntimeSettings(ApiModel):
    provider: str
    model: str
    openai_base_url: str | None = None
    openai_profile_id: str | None = None
    agent_profile: str
    tool_mode: str
    reasoning_effort: str = "medium"
    reasoning_fast: bool = False
    recursion_limit: int = 100_000
    max_sdk_turns: int = 500
    group_tool_traces: bool = True
    tool_trace_detail_limit: int = 1
    background_watch_timeout_s: int = 7200
    interrupt_drain_timeout_s: int = 10
    parallel_max_threads: int = 5
    tool_health_enabled: bool = True
    tool_health_fail_threshold: int = 2
    tool_health_suppress_seconds: int = 900
    plan_mode: bool = False


class UpdateRuntimeSettingsRequest(ApiModel):
    provider: str | None = None
    model: str | None = None
    openai_base_url: str | None = None
    agent_profile: str | None = None
    tool_mode: str | None = None
    reasoning_effort: str | None = None
    reasoning_fast: bool | None = None
    recursion_limit: int | None = None
    max_sdk_turns: int | None = None
    group_tool_traces: bool | None = None
    tool_trace_detail_limit: int | None = None
    background_watch_timeout_s: int | None = None
    interrupt_drain_timeout_s: int | None = None
    parallel_max_threads: int | None = None
    tool_health_enabled: bool | None = None
    tool_health_fail_threshold: int | None = None
    tool_health_suppress_seconds: int | None = None
    plan_mode: bool | None = None


class OnboardingSettings(ApiModel):
    completed: bool = False
    step: int = 0


class UpdateOnboardingSettingsRequest(ApiModel):
    completed: bool | None = None
    step: int | None = None


class SandboxSettings(ApiModel):
    backend: str = "builtin"
    modal_app: str = "sandwalk"
    cpu_image: str = "python:3.12-slim"
    gpu_image: str = "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"
    pip_packages: str = "pandas,numpy,scipy,scikit-learn,matplotlib,seaborn"
    compute_type: str = "cpu"
    gpu_class: str = "T4"
    cpu_cores: float = 2.0
    ram_gb: float = 8.0
    idle_ttl_seconds: int = 600
    modal_configured: bool = False


class UpdateSandboxSettingsRequest(ApiModel):
    backend: str | None = None
    modal_app: str | None = None
    cpu_image: str | None = None
    gpu_image: str | None = None
    pip_packages: str | None = None
    compute_type: str | None = None
    gpu_class: str | None = None
    cpu_cores: float | None = None
    ram_gb: float | None = None
    idle_ttl_seconds: int | None = None


class SandboxProbeStep(ApiModel):
    name: str
    ok: bool
    detail: str


class SandboxProbeReport(ApiModel):
    ok: bool
    skipped: bool = False
    steps: list[SandboxProbeStep] = Field(default_factory=list)


class PromptBudgetBucket(ApiModel):
    id: str
    label: str
    tokens: int = 0
    chars: int = 0
    count: int | None = None
    children: list[PromptBudgetBucket] = Field(default_factory=list)


class PromptBudgetToolCounts(ApiModel):
    domain: int = 0
    mcp: int = 0
    deepagents: int = 0
    total: int = 0
    openai_cap: int = 128


class PromptBudgetResponse(ApiModel):
    total_tokens: int = 0
    total_chars: int = 0
    tokenizer: str = "chars/4"
    tool_mode: str = "ptc"
    provider: str | None = None
    model: str | None = None
    specialist_id: str | None = None
    specialist_name: str | None = None
    tool_counts: PromptBudgetToolCounts = Field(default_factory=PromptBudgetToolCounts)
    buckets: list[PromptBudgetBucket] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sample_query: str = "Hello"
