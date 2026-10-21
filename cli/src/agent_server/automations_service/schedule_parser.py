"""Schedule parser for natural-language, interval, one-shot, and 5-field cron expressions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from agent_server.models.automations import AutomationScheduleKind

_WEEKDAY_MAP = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}

_CRON_DOW_MAP = {
    "sun": 0,
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
}


@dataclass(frozen=True)
class ParsedSchedule:
    expr: str
    kind: AutomationScheduleKind
    label: str
    interval_seconds: int | None = None
    cron_fields: tuple[str, str, str, str, str] | None = None
    once_at: datetime | None = None


def _parse_time_token(token: str) -> tuple[int, int]:
    t = token.strip().lower()
    if t == "noon":
        return 12, 0
    if t == "midnight":
        return 0, 0
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", t)
    if not m:
        raise ValueError(f"Invalid time expression: {token!r}")
    hour = int(m.group(1))
    minute = int(m.group(2) or "0")
    ampm = m.group(3)
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Time out of range: {token!r}")
    return hour, minute


def _format_time_12h(hour: int, minute: int) -> str:
    suffix = "AM" if hour < 12 else "PM"
    h12 = hour % 12 or 12
    return f"{h12}:{minute:02d} {suffix}"


def _parse_duration_seconds(num_str: str | None, unit_str: str) -> tuple[int, str]:
    n = int(num_str) if num_str else 1
    if n <= 0:
        raise ValueError("Duration must be positive.")
    u = unit_str.strip().lower()
    if u in {"s", "sec", "secs", "second", "seconds"}:
        return n, f"{n}s"
    if u in {"m", "min", "mins", "minute", "minutes"}:
        return n * 60, f"{n}m" if n != 1 else "minute"
    if u in {"h", "hr", "hrs", "hour", "hours"}:
        return n * 3600, f"{n}h" if n != 1 else "hour"
    if u in {"d", "day", "days"}:
        return n * 86400, f"{n}d" if n != 1 else "day"
    if u in {"w", "wk", "week", "weeks"}:
        return n * 604800, f"{n}w" if n != 1 else "week"
    raise ValueError(f"Unknown duration unit: {unit_str!r}")


def parse_schedule(raw: str, *, now: datetime | None = None) -> ParsedSchedule:
    """Parse a schedule string into a normalized :class:`ParsedSchedule`."""
    ref = now or datetime.now(UTC)
    text = (raw or "").strip()
    if not text:
        text = "every 1h"
    lowered = text.lower()

    if lowered in {"webhook", "event", "manual"}:
        return ParsedSchedule(expr="webhook", kind="webhook", label="Webhook triggered")

    # 1. One-shot relative delay: "in 30m", "in 2 hours", "in 1d"
    m_in = re.match(
        r"^in\s+(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)$",
        lowered,
    )
    if m_in:
        secs, label_unit = _parse_duration_seconds(m_in.group(1), m_in.group(2))
        target = ref + timedelta(seconds=secs)
        return ParsedSchedule(
            expr=text,
            kind="once",
            label=f"Once in {label_unit}",
            interval_seconds=secs,
            once_at=target,
        )

    # 2. ISO timestamp one-shot: "2026-10-21T09:00:00"
    if re.match(r"^\d{4}-\d{2}-\d{2}[tT ]\d{2}:\d{2}", text):
        try:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return ParsedSchedule(
                expr=text,
                kind="once",
                label=f"Once at {dt.strftime('%Y-%m-%d %H:%M UTC')}",
                once_at=dt,
            )
        except ValueError as exc:
            raise ValueError(f"Invalid ISO timestamp: {text!r}") from exc

    # 3. Simple aliases: "hourly", "daily", "weekly"
    if lowered == "hourly":
        return ParsedSchedule(
            expr="every 1h",
            kind="interval",
            label="Every hour",
            interval_seconds=3600,
        )
    if lowered == "daily":
        return ParsedSchedule(
            expr="0 9 * * *",
            kind="cron",
            label="Daily at 9:00 AM",
            cron_fields=("0", "9", "*", "*", "*"),
        )
    if lowered == "weekly":
        return ParsedSchedule(
            expr="0 9 * * 1",
            kind="cron",
            label="Weekly on Mondays at 9:00 AM",
            cron_fields=("0", "9", "*", "*", "1"),
        )

    # 4. Recurring interval: "every 15m", "every 2h", "every hour", "30m"
    m_every = re.match(
        r"^(?:every\s+)?(\d+)?\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|wk|week|weeks)$",
        lowered,
    )
    if m_every and (lowered.startswith("every ") or m_every.group(1)):
        secs, label_unit = _parse_duration_seconds(m_every.group(1), m_every.group(2))
        label = f"Every {label_unit}"
        return ParsedSchedule(
            expr=text,
            kind="interval",
            label=label,
            interval_seconds=secs,
        )

    # 5. Natural day/time schedules:
    # - "every day at 9am", "daily at 8:30am", "every morning at 9:00"
    m_daily = re.match(
        r"^(?:every\s+(?:day|morning|evening)|daily)(?:\s+at)?\s+(.+)$",
        lowered,
    )
    if m_daily:
        hour, minute = _parse_time_token(m_daily.group(1))
        return ParsedSchedule(
            expr=f"{minute} {hour} * * *",
            kind="cron",
            label=f"Daily at {_format_time_12h(hour, minute)}",
            cron_fields=(str(minute), str(hour), "*", "*", "*"),
        )

    # - "weekdays at 9am" / "weekends at 10am"
    m_wk = re.match(r"^(weekdays|weekends)(?:\s+at)?\s+(.+)$", lowered)
    if m_wk:
        kind_wk = m_wk.group(1)
        hour, minute = _parse_time_token(m_wk.group(2))
        dow = "1-5" if kind_wk == "weekdays" else "0,6"
        title_wk = "Weekdays" if kind_wk == "weekdays" else "Weekends"
        return ParsedSchedule(
            expr=f"{minute} {hour} * * {dow}",
            kind="cron",
            label=f"{title_wk} at {_format_time_12h(hour, minute)}",
            cron_fields=(str(minute), str(hour), "*", "*", dow),
        )

    # - "every monday at 9am", "monday, wednesday at 9am"
    m_dow = re.match(
        r"^(?:every\s+)?([a-z,\s]+?)(?:\s+at)?\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|noon|midnight)$",
        lowered,
    )
    if m_dow:
        day_tokens = [
            d.strip()
            for d in re.split(r"[,\s]+", m_dow.group(1))
            if d.strip() and d.strip() != "and"
        ]
        if day_tokens and all(d in _WEEKDAY_MAP for d in day_tokens):
            hour, minute = _parse_time_token(m_dow.group(2))
            cron_dows = sorted({(_WEEKDAY_MAP[d] + 1) % 7 for d in day_tokens})
            dow_field = ",".join(str(d) for d in cron_dows)
            day_names = ", ".join(d.capitalize() for d in day_tokens)
            return ParsedSchedule(
                expr=f"{minute} {hour} * * {dow_field}",
                kind="cron",
                label=f"Every {day_names} at {_format_time_12h(hour, minute)}",
                cron_fields=(str(minute), str(hour), "*", "*", dow_field),
            )

    # 6. Standard 5-field cron expression: "0 9 * * 1-5" or "*/15 * * * *"
    parts = text.split()
    if len(parts) == 5:
        c_min, c_hour, c_dom, c_mon, c_dow = parts
        # Validate fields can be expanded
        _expand_cron_field(c_min, 0, 59)
        _expand_cron_field(c_hour, 0, 23)
        _expand_cron_field(c_dom, 1, 31)
        _expand_cron_field(c_mon, 1, 12)
        _expand_cron_dow(c_dow)
        return ParsedSchedule(
            expr=text,
            kind="cron",
            label=_describe_cron(c_min, c_hour, c_dom, c_mon, c_dow),
            cron_fields=(c_min, c_hour, c_dom, c_mon, c_dow),
        )

    raise ValueError(
        f"Unrecognized schedule {raw!r}. Examples: 'every 15m', 'in 30m', 'daily at 9am', 'weekdays at 8:30am', or '0 9 * * 1-5'."
    )


def _expand_cron_field(field: str, min_val: int, max_val: int) -> set[int]:
    result: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            base, step_str = part.split("/", 1)
            step = int(step_str)
            if step <= 0:
                raise ValueError(f"Invalid cron step in {field!r}")
        else:
            base = part
        if base == "*":
            start, end = min_val, max_val
        elif "-" in base:
            s_str, e_str = base.split("-", 1)
            start, end = int(s_str), int(e_str)
        else:
            val = int(base)
            start, end = val, val
        if start < min_val or end > max_val or start > end:
            raise ValueError(f"Cron field {field!r} out of range [{min_val}..{max_val}]")
        result.update(range(start, end + 1, step))
    return result


def _expand_cron_dow(field: str) -> set[int]:
    normalized = field.lower()
    for name, idx in _CRON_DOW_MAP.items():
        normalized = re.sub(rf"\b{name}\b", str(idx), normalized)
    raw = _expand_cron_field(normalized.replace("7", "0"), 0, 6)
    # Convert cron DOW (0=Sun, 1=Mon..6=Sat) -> Python weekday (0=Mon..6=Sun)
    return {(d - 1) % 7 for d in raw}


def _describe_cron(c_min: str, c_hour: str, c_dom: str, c_mon: str, c_dow: str) -> str:
    if c_dom == "*" and c_mon == "*":
        if c_min.isdigit() and c_hour.isdigit():
            time_str = _format_time_12h(int(c_hour), int(c_min))
            if c_dow == "*":
                return f"Daily at {time_str}"
            if c_dow in {"1-5", "mon-fri"}:
                return f"Weekdays at {time_str}"
            if c_dow in {"0,6", "6,0", "sat,sun"}:
                return f"Weekends at {time_str}"
        if c_min.startswith("*/") and c_hour == "*" and c_dow == "*":
            return f"Every {c_min[2:]}m"
    return f"Cron ({c_min} {c_hour} {c_dom} {c_mon} {c_dow})"


def compute_next_run(
    schedule_expr: str,
    *,
    after: datetime | None = None,
) -> datetime | None:
    """Compute the next UTC fire timestamp after ``after``."""
    ref = after or datetime.now(UTC)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=UTC)
    parsed = parse_schedule(schedule_expr, now=ref)

    if parsed.kind == "webhook":
        return None
    if parsed.kind == "once":
        return parsed.once_at
    if parsed.kind == "interval":
        secs = parsed.interval_seconds or 3600
        return ref + timedelta(seconds=secs)
    if parsed.kind == "cron" and parsed.cron_fields is not None:
        c_min, c_hour, c_dom, c_mon, c_dow = parsed.cron_fields
        mins = _expand_cron_field(c_min, 0, 59)
        hours = _expand_cron_field(c_hour, 0, 23)
        doms = _expand_cron_field(c_dom, 1, 31)
        mons = _expand_cron_field(c_mon, 1, 12)
        dows = _expand_cron_dow(c_dow)

        candidate = (ref + timedelta(minutes=1)).replace(second=0, microsecond=0)
        # Search up to 366 days ahead
        for _ in range(366 * 24 * 60):
            if (
                candidate.month in mons
                and candidate.day in doms
                and candidate.weekday() in dows
                and candidate.hour in hours
                and candidate.minute in mins
            ):
                return candidate
            candidate += timedelta(minutes=1)
    return ref + timedelta(hours=1)
