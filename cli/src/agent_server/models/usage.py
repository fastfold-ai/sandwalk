"""API models for /v1/usage/*."""

from __future__ import annotations

from agent_server.models.base import ApiModel


class UsageDayPoint(ApiModel):
    day: str
    tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cli_tokens: int = 0
    ui_tokens: int = 0
    slack_tokens: int = 0
    unknown_tokens: int = 0
    runs: int = 0


class UsageModelRow(ApiModel):
    model_id: str
    provider: str = "unknown"
    tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    runs: int = 0
    messages: int = 0


class UsageChartModel(ApiModel):
    """Stable chart series identity (provider + model)."""

    model_id: str
    provider: str = "unknown"


class UsageModelDayPoint(ApiModel):
    """Per-day token total for one provider/model (Last 30 days chart)."""

    day: str
    model_id: str
    provider: str = "unknown"
    tokens: int = 0


class UsageOverview(ApiModel):
    lifetime_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    peak_day_tokens: int = 0
    peak_day: str | None = None
    models_used: int = 0
    runs: int = 0
    sessions: int = 0
    messages: int = 0
    avg_tokens_per_session: int = 0
    # Cursor-style activity metrics.
    longest_agent_seconds: int = 0
    longest_streak_days: int = 0
    current_streak_days: int = 0
    cli_tokens: int = 0
    ui_tokens: int = 0
    slack_tokens: int = 0
    unknown_tokens: int = 0
    cli_share: float = 0.0
    ui_share: float = 0.0
    days: list[UsageDayPoint]
    top_models: list[UsageModelRow]
    # Last-30-day stacked chart: day×model tokens + stable model order for colors.
    model_days: list[UsageModelDayPoint] = []
    chart_models: list[UsageChartModel] = []
    backfilled: bool = False


class UsageBackfillResponse(ApiModel):
    ok: bool = True
    runs_upserted: int = 0
    from_events: int = 0
    from_trajectories: int = 0
