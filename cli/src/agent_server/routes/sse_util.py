"""Shared SSE framing for WKWebView (Tauri) flush padding."""

WKWEBVIEW_PAD = ":" + (" " * 8192) + "\n\n"


def sse_data(payload: str, *, event_id: str | None = None) -> str:
    prefix = f"id: {event_id}\n" if event_id else ""
    return f"{prefix}data: {payload}\n\n" + WKWEBVIEW_PAD
