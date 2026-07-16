"""Small string-formatting helpers used by trace rendering."""

from __future__ import annotations


def format_args(args: dict | None, max_value_len: int = 50) -> str:
    """Format tool arguments as a compact key=value string.

    Omits internal keys (starting with ``_``) and truncates long values.
    """
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        if k.startswith("_"):
            continue
        v_str = str(v)
        if len(v_str) > max_value_len:
            v_str = v_str[:max_value_len] + "..."
        if isinstance(v, str):
            parts.append(f'{k}="{v_str}"')
        else:
            parts.append(f"{k}={v_str}")
    return ", ".join(parts)


def truncate_output(text: str, max_chars: int = 200) -> str:
    """Truncate tool output text, appending length info if trimmed."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"... [{len(text)} chars total]"


def format_duration(seconds: float) -> str:
    """Format an elapsed duration with a sensible unit.

    Sub-second durations show milliseconds (e.g. ``42ms``) so fast tool calls
    don't all collapse to ``0.0s``; longer ones show seconds or ``m s``.
    """
    seconds = max(0.0, float(seconds))
    if seconds < 1:
        return f"{int(round(seconds * 1000))}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"
