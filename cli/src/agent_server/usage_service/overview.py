"""Aggregate usage_runs into Overview API payload."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from agent_server.models.usage import (
    UsageChartModel,
    UsageDayPoint,
    UsageModelDayPoint,
    UsageModelRow,
    UsageOverview,
)
from agent_server.store import AgentStore
from agent_server.usage_service.backfill import ensure_backfill
from agent_server.usage_service.parse import canonicalize_usage_model

_CHART_WINDOW_DAYS = 30
_CHART_TOP_MODELS = 7


def _share(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(part / total, 4)


def _as_datetime(value: object | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _span_seconds(start: datetime | None, end: datetime | None) -> int:
    if start is None or end is None:
        return 0
    if start.tzinfo is not None and end.tzinfo is None:
        end = end.replace(tzinfo=start.tzinfo)
    elif start.tzinfo is None and end.tzinfo is not None:
        start = start.replace(tzinfo=end.tzinfo)
    return max(0, int((end - start).total_seconds()))


def _longest_agent_seconds(
    store: AgentStore, *, session_ids: set[str] | None = None
) -> int:
    """Longest usage-ledger span per session (not a full events table scan).

    Scanning ``events`` for tool/run rows contends with live benches on the
    same SQLite WAL and stalls Overview. The ledger is enough for the metric.
    """
    allow = session_ids
    if allow is not None and not allow:
        return 0
    best = 0
    try:
        with store._connect() as connection:  # type: ignore[attr-defined]
            if allow is not None:
                ph = ",".join("?" for _ in allow)
                rows = connection.execute(
                    f"""
                    SELECT session_id, MIN(updated_at) AS t0, MAX(updated_at) AS t1
                    FROM usage_runs
                    WHERE session_id IN ({ph})
                    GROUP BY session_id
                    """,
                    tuple(allow),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT u.session_id, MIN(u.updated_at) AS t0, MAX(u.updated_at) AS t1
                    FROM usage_runs u
                    INNER JOIN sessions s ON s.id = u.session_id
                    WHERE COALESCE(s.source, '') != 'bench'
                    GROUP BY u.session_id
                    """
                ).fetchall()
        for row in rows:
            secs = _span_seconds(
                _as_datetime(row["t0"]), _as_datetime(row["t1"])
            )
            if secs > best:
                best = secs
    except Exception:
        pass
    return max(0, best)


def _streaks(active_days: set[date], today: date) -> tuple[int, int]:
    """Return (longest_streak_days, current_streak_days)."""
    if not active_days:
        return 0, 0
    ordered = sorted(active_days)
    longest = run = 1
    for index in range(1, len(ordered)):
        if ordered[index] == ordered[index - 1] + timedelta(days=1):
            run += 1
            if run > longest:
                longest = run
        else:
            run = 1

    end = today if today in active_days else today - timedelta(days=1)
    if end not in active_days:
        return longest, 0
    current = 0
    cursor = end
    while cursor in active_days:
        current += 1
        cursor -= timedelta(days=1)
    return longest, current


def _series_key(provider: str, model_id: str) -> str:
    return f"{provider}\t{model_id}"


def _row_identity(row: dict) -> tuple[str, str]:
    provider, model_id = canonicalize_usage_model(
        row.get("model_id"), row.get("provider")
    )
    if model_id == "unknown":
        return "unknown", "Other"
    return provider, model_id


def _build_model_chart(
    rows: list[dict],
    *,
    today: date,
) -> tuple[list[UsageModelDayPoint], list[UsageChartModel]]:
    """Last 30 days stacked-bar series: top provider/models + Other."""
    start = today - timedelta(days=_CHART_WINDOW_DAYS - 1)
    totals: dict[str, int] = defaultdict(int)
    by_day_model: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    labels: dict[str, tuple[str, str]] = {}

    for row in rows:
        day = str(row.get("day") or "")
        try:
            day_date = date.fromisoformat(day)
        except ValueError:
            continue
        if day_date < start or day_date > today:
            continue
        tokens = int(row.get("input_tokens") or 0) + int(row.get("output_tokens") or 0)
        if tokens <= 0:
            continue
        provider, model_id = _row_identity(row)
        key = _series_key(provider, model_id)
        labels[key] = (provider, model_id)
        totals[key] += tokens
        by_day_model[day][key] += tokens

    other_key = _series_key("unknown", "Other")
    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    top = [key for key, _ in ranked if key != other_key][:_CHART_TOP_MODELS]
    top_set = set(top)
    chart_keys = list(top)
    if any(key not in top_set for key in totals):
        chart_keys.append(other_key)
        labels[other_key] = ("unknown", "Other")

    model_days: list[UsageModelDayPoint] = []
    cursor = start
    while cursor <= today:
        key = cursor.isoformat()
        day_bucket = by_day_model.get(key) or {}
        rolled: dict[str, int] = defaultdict(int)
        for series, tokens in day_bucket.items():
            bucket = series if series in top_set else other_key
            rolled[bucket] += tokens
        for series in chart_keys:
            tokens = int(rolled.get(series) or 0)
            if tokens <= 0:
                continue
            provider, model_id = labels[series]
            model_days.append(
                UsageModelDayPoint(
                    day=key,
                    model_id=model_id,
                    provider=provider,
                    tokens=tokens,
                )
            )
        cursor += timedelta(days=1)

    chart_models = [
        UsageChartModel(model_id=labels[key][1], provider=labels[key][0])
        for key in chart_keys
    ]
    return model_days, chart_models


def build_usage_overview(
    store: AgentStore, *, project_id: str | None = None
) -> UsageOverview:
    backfilled = ensure_backfill(store)
    scoped = (project_id or "").strip() or None
    rows = store.list_usage_runs(project_id=scoped)
    if not rows:
        return UsageOverview(
            days=[], top_models=[], model_days=[], chart_models=[], backfilled=backfilled
        )

    today = date.today()
    start = today - timedelta(days=52 * 7 + 6)

    by_day: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "input": 0,
            "output": 0,
            "cache": 0,
            "cli": 0,
            "ui": 0,
            "slack": 0,
            "unknown": 0,
            "runs": 0,
        }
    )
    by_model: dict[str, dict[str, int | str]] = defaultdict(
        lambda: {"input": 0, "output": 0, "runs": 0, "provider": "unknown", "model_id": ""}
    )
    session_ids: set[str] = set()
    active_days: set[date] = set()
    lifetime_in = lifetime_out = lifetime_cache = 0
    surface_totals = {"cli": 0, "ui": 0, "slack": 0, "unknown": 0}

    for row in rows:
        day = str(row.get("day") or "")
        try:
            day_date = date.fromisoformat(day)
        except ValueError:
            continue
        inp = int(row.get("input_tokens") or 0)
        out = int(row.get("output_tokens") or 0)
        cache = int(row.get("cache_read_tokens") or 0)
        total = inp + out
        surface = str(row.get("surface") or "unknown")
        if surface not in surface_totals:
            surface = "unknown"
        lifetime_in += inp
        lifetime_out += out
        lifetime_cache += cache
        surface_totals[surface] += total
        session_ids.add(str(row.get("session_id") or ""))
        if total > 0:
            active_days.add(day_date)
        provider, model_id = _row_identity(row)
        if model_id != "Other":
            key = _series_key(provider, model_id)
            by_model[key]["input"] = int(by_model[key]["input"]) + inp
            by_model[key]["output"] = int(by_model[key]["output"]) + out
            by_model[key]["runs"] = int(by_model[key]["runs"]) + 1
            by_model[key]["provider"] = provider
            by_model[key]["model_id"] = model_id
        if start <= day_date <= today:
            bucket = by_day[day]
            bucket["input"] += inp
            bucket["output"] += out
            bucket["cache"] += cache
            bucket[surface] += total
            bucket["runs"] += 1

    days: list[UsageDayPoint] = []
    peak_day = None
    peak_tokens = 0
    cursor = start
    while cursor <= today:
        key = cursor.isoformat()
        bucket = by_day.get(key)
        tokens = 0
        point = UsageDayPoint(day=key)
        if bucket:
            tokens = int(bucket["input"] + bucket["output"])
            point = UsageDayPoint(
                day=key,
                tokens=tokens,
                input_tokens=int(bucket["input"]),
                output_tokens=int(bucket["output"]),
                cache_read_tokens=int(bucket["cache"]),
                cli_tokens=int(bucket["cli"]),
                ui_tokens=int(bucket["ui"]),
                slack_tokens=int(bucket["slack"]),
                unknown_tokens=int(bucket["unknown"]),
                runs=int(bucket["runs"]),
            )
        days.append(point)
        if tokens > peak_tokens:
            peak_tokens = tokens
            peak_day = key
        cursor += timedelta(days=1)

    top_models = sorted(
        (
            UsageModelRow(
                model_id=str(vals["model_id"]),
                provider=str(vals["provider"]),
                tokens=int(vals["input"]) + int(vals["output"]),
                input_tokens=int(vals["input"]),
                output_tokens=int(vals["output"]),
                runs=int(vals["runs"]),
                messages=int(vals["runs"]),
            )
            for vals in by_model.values()
            if str(vals["model_id"]) not in {"", "unknown", "Other"}
        ),
        key=lambda row: (-row.tokens, row.provider, row.model_id),
    )[:5]

    model_days, chart_models = _build_model_chart(rows, today=today)

    lifetime = lifetime_in + lifetime_out
    sessions = len({sid for sid in session_ids if sid})
    messages = store.count_messages_for_sessions(list(session_ids)) if sessions else 0
    attributed = surface_totals["cli"] + surface_totals["ui"]
    longest_streak, current_streak = _streaks(active_days, today)

    return UsageOverview(
        lifetime_tokens=lifetime,
        input_tokens=lifetime_in,
        output_tokens=lifetime_out,
        cache_read_tokens=lifetime_cache,
        peak_day_tokens=peak_tokens,
        peak_day=peak_day,
        models_used=len(by_model),
        runs=len(rows),
        sessions=sessions,
        messages=messages,
        avg_tokens_per_session=(lifetime // sessions) if sessions else 0,
        longest_agent_seconds=_longest_agent_seconds(
            store,
            session_ids={sid for sid in session_ids if sid} if scoped else None,
        ),
        longest_streak_days=longest_streak,
        current_streak_days=current_streak,
        cli_tokens=surface_totals["cli"],
        ui_tokens=surface_totals["ui"],
        slack_tokens=surface_totals["slack"],
        unknown_tokens=surface_totals["unknown"],
        cli_share=_share(surface_totals["cli"], attributed),
        ui_share=_share(surface_totals["ui"], attributed),
        days=days,
        top_models=top_models,
        model_days=model_days,
        chart_models=chart_models,
        backfilled=backfilled,
    )
