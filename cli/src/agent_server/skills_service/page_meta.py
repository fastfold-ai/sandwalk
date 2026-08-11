"""Scrape public skills.sh skill pages for Summary / stars / first-seen.

The authenticated ``/api/v1/skills/{source}/{skill}`` response only returns
files + installs. The rich Summary, GitHub stars, and First Seen shown on
https://www.skills.sh/{source}/{skill} are SSR HTML — scrape them from the
public page (same approach as the All Time badge on the homepage).
"""

from __future__ import annotations

import html as html_lib
import re
import time
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request

from agent_server.skills_service.auth import SKILLS_SH_BASE_URL

_PAGE_META_TTL_S = 300.0
_page_meta_cache: dict[str, tuple[float, dict[str, object]]] = {}

_SUMMARY_BLOCK_RE = re.compile(
    r">Summary</div>(.*?)<span>SKILL\.md</span>",
    re.IGNORECASE | re.DOTALL,
)
_STRONG_RE = re.compile(r"<strong>(.*?)</strong>", re.IGNORECASE | re.DOTALL)
_LI_RE = re.compile(r"<li>(.*?)</li>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_STARS_RE = re.compile(
    r"GitHub Stars</span></div>.*?<span>([0-9]+(?:\.[0-9]+)?[KMB]?)</span>",
    re.IGNORECASE | re.DOTALL,
)
_FIRST_SEEN_RE = re.compile(
    r"First Seen</span></div><div[^>]*>([^<]+)</div>",
    re.IGNORECASE,
)
_COMPACT_COUNT_RE = re.compile(
    r"^([0-9]*\.?[0-9]+)\s*([KMB])?$",
    re.IGNORECASE,
)


def _strip_tags(value: str) -> str:
    text = _TAG_RE.sub("", value)
    return html_lib.unescape(text).strip()


def parse_compact_count(value: str) -> int | None:
    text = str(value or "").strip().replace(",", "")
    match = _COMPACT_COUNT_RE.fullmatch(text)
    if not match:
        return None
    number = float(match.group(1))
    suffix = (match.group(2) or "").upper()
    scale = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
    return int(number * scale)


def parse_skills_sh_page_meta(body: str) -> dict[str, object]:
    """Parse summary markdown, github_stars, and first_seen from page HTML."""
    summary: str | None = None
    block_match = _SUMMARY_BLOCK_RE.search(body or "")
    if block_match:
        block = block_match.group(1)
        lines: list[str] = []
        strong = _STRONG_RE.search(block)
        if strong:
            headline = _strip_tags(strong.group(1))
            if headline:
                lines.append(f"**{headline}**")
        bullets = [_strip_tags(item) for item in _LI_RE.findall(block)]
        bullets = [item for item in bullets if item]
        if bullets:
            if lines:
                lines.append("")
            lines.extend(f"- {item}" for item in bullets)
        if not lines:
            # Fallback: plain text from the summary card.
            plain = _strip_tags(block)
            if plain:
                lines.append(plain)
        if lines:
            summary = "\n".join(lines).strip()

    github_stars: int | None = None
    stars_match = _STARS_RE.search(body or "")
    if stars_match:
        github_stars = parse_compact_count(stars_match.group(1))

    first_seen: str | None = None
    first_match = _FIRST_SEEN_RE.search(body or "")
    if first_match:
        text = first_match.group(1).strip()
        if text:
            first_seen = text

    return {
        "summary": summary,
        "github_stars": github_stars,
        "first_seen": first_seen,
    }


def fetch_skills_sh_page_meta(source: str, skill: str) -> dict[str, object]:
    """Fetch and cache public page metadata for a skill."""
    source_value = str(source or "").strip().strip("/")
    skill_value = str(skill or "").strip().strip("/")
    if not source_value or not skill_value:
        return {"summary": None, "github_stars": None, "first_seen": None}

    cache_key = f"{source_value}/{skill_value}".lower()
    now = time.time()
    cached = _page_meta_cache.get(cache_key)
    if cached is not None:
        cached_at, payload = cached
        if now - cached_at < _PAGE_META_TTL_S:
            return payload

    import agent_server.skills_service as skills_service

    url = (
        f"{SKILLS_SH_BASE_URL}/"
        f"{quote(source_value, safe='/')}/{quote(skill_value, safe='')}"
    )
    request = Request(
        url,
        headers={
            "Accept": "text/html",
            "User-Agent": "sandwalk-skills-detail/1.0",
        },
        method="GET",
    )
    try:
        with skills_service.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError):
        if cached is not None:
            return cached[1]
        return {"summary": None, "github_stars": None, "first_seen": None}

    payload = parse_skills_sh_page_meta(body)
    _page_meta_cache[cache_key] = (now, payload)
    return payload
