"""Shared template for "you can close this tab" pages after a connector's
browser-based OAuth finishes.

Slack's one-click flow is the first user (``slack_oauth_return.py``), but any
connector that sends the browser through a hosted OAuth exchange before
landing back on this machine can reuse ``render_oauth_return_page`` - just
supply its own icon and copy, and register a route that calls it.
"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "assets"

# The waveform mark from Sandwalk's own brand assets (apps/local-web/public/
# brand/aura_icon.svg) - inlined so this page has no static-file dependency at
# all, since it can render before any UI dist is mounted.
_SANDWALK_ICON_SVG = """<svg viewBox="0 0 847 847" fill="none" xmlns="http://www.w3.org/2000/svg">
<g fill="currentColor">
<path d="M739 248c-19 0-35 16-35 35v70c0 19 16 35 35 35s35-16 35-35v-70c0-19-16-35-35-35z"/>
<path d="M318 177c-19 0-35 16-35 35v246c0 19 16 35 35 35s35-16 35-35V212c0-19-16-35-35-35z"/>
<path d="M213 283c-19 0-35 16-35 35v176c0 19 16 35 35 35s35-16 35-35V318c0-19-16-35-35-35z"/>
<path d="M107 458c-19 0-35 16-35 35v70c0 19 16 35 35 35s35-16 35-35v-70c0-19-16-35-35-35z"/>
<path d="M422 265c-19 0-35 16-35 35v246c0 19 16 35 35 35s35-16 35-35V300c0-19-16-35-35-35z"/>
<path d="M634 318c-19 0-35 16-35 35v178c0 19 16 35 35 35s35-16 35-35V353c0-19-16-35-35-35z"/>
<path d="M529 353c-19 0-35 16-35 35v246c0 19 16 35 35 35s35-16 35-35V388c0-19-16-35-35-35z"/>
</g>
</svg>"""

# 24x24 check / x, drawn to match rather than relying on font glyph rendering
# (which varies enough across platforms to look off-center).
_CHECK_SVG = """<svg viewBox="0 0 24 24" fill="none"><path d="M5 12.5l4.5 4.5L19 7" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>"""
_X_SVG = """<svg viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>"""


@lru_cache(maxsize=8)
def connector_icon_data_uri(filename: str) -> str:
    """Base64 data URI for an icon dropped in ``routes/assets/``.

    Bundled into the wheel automatically (hatchling includes everything under
    the package path), so a new connector just needs its icon file added
    there - no packaging config to touch.
    """
    path = ASSETS_DIR / filename
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    ext = path.suffix.lstrip(".") or "png"
    mime = "svg+xml" if ext == "svg" else ext
    return f"data:image/{mime};base64,{encoded}"


def render_oauth_return_page(
    *,
    ok: bool,
    title: str,
    detail: str,
    tag_label: str | None = None,
    tag_icon_data_uri: str | None = None,
) -> str:
    """The "you can close this tab" page shown after a connector's OAuth.

    ``tag_label``/``tag_icon_data_uri`` describe the thing that got connected
    (e.g. "Slack workspace" + Slack's logo) and are shown as a small pill
    below the result - omit them to render a plain result page.
    """
    glow = "rgba(120, 219, 165, 0.16)" if ok else "rgba(255, 99, 99, 0.14)"
    ring = "rgba(120, 219, 165, 0.35)" if ok else "rgba(255, 99, 99, 0.3)"
    icon_color = "#7bdba5" if ok else "#ff7a7a"
    status_svg = _CHECK_SVG if ok else _X_SVG

    tag = ""
    if tag_label:
        icon = f'<img src="{tag_icon_data_uri}" alt="" />' if tag_icon_data_uri else ""
        tag = f'<div class="tag">{icon}{tag_label}</div>'

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>sandwalk</title>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ height: 100%; }}
  body {{
    font-family: -apple-system, "SF Pro Text", system-ui, sans-serif;
    background:
      radial-gradient(circle at 50% 38%, rgba(120,219,165,0.06), transparent 60%),
      #0a0a0d;
    color: #f2f2f3;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0;
  }}
  .stage {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.1rem;
    padding: 2rem;
    text-align: center;
  }}
  .wordmark {{
    display: flex;
    align-items: center;
    gap: 0.4rem;
    color: #6f6f78;
    font-size: 0.78rem;
    font-weight: 600;
    margin-bottom: 0.4rem;
  }}
  .wordmark svg {{ width: 13px; height: 13px; opacity: 0.8; }}
  .status {{
    width: 84px;
    height: 84px;
    border-radius: 999px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: {glow};
    box-shadow: inset 0 0 0 1px {ring};
  }}
  .status svg {{
    width: 32px;
    height: 32px;
    color: {icon_color};
  }}
  .copy h1 {{
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0 0 0.4rem;
    letter-spacing: -0.01em;
  }}
  .copy p {{
    color: #8b8b93;
    font-size: 0.9rem;
    line-height: 1.5;
    margin: 0;
    max-width: 21rem;
  }}
  .tag {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.32rem 0.7rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    color: #b3b3ba;
    font-size: 0.75rem;
    font-weight: 500;
    margin-top: 0.3rem;
  }}
  .tag img {{ width: 13px; height: 13px; border-radius: 3px; }}
</style>
</head>
<body>
  <div class="stage">
    <div class="wordmark">{_SANDWALK_ICON_SVG} sandwalk</div>
    <div class="status">{status_svg}</div>
    <div class="copy">
      <h1>{title}</h1>
      <p>{detail}</p>
    </div>
    {tag}
  </div>
</body>
</html>"""
