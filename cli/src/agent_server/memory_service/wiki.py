"""Living Markdown Wiki with [[wikilinks]], backlinks, and bounded TOC."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from agent_server.memory_service.store import memory_root, normalize_scope
from agent_server.models.memory import WikiPageDetail, WikiPageList, WikiPageSummary

_WIKILINK_RE = re.compile(r"\[\[([^\[\]|]+)(?:\|[^\[\]]+)?\]\]")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug or "page"


def _wiki_dir_for_scope(scope: str, project_folder: Path | None = None) -> Path:
    norm = normalize_scope(scope)
    if project_folder is not None and project_folder.is_dir():
        target = project_folder / ".sandwalk" / "wiki"
        target.mkdir(parents=True, exist_ok=True)
        return target
    root = memory_root() / "wiki"
    if norm.startswith("project:"):
        pid = norm.split(":", 1)[1]
        target = root / "projects" / pid
    elif norm.startswith("specialist:"):
        sid = norm.split(":", 1)[1]
        target = root / "specialists" / sid
    else:
        target = root / "global"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _parse_markdown_page(path: Path, scope: str) -> WikiPageDetail:
    raw = path.read_text(encoding="utf-8", errors="replace")
    title = path.stem.replace("-", " ").title()
    summary = ""
    tags: list[str] = []
    body = raw

    if raw.startswith("---\n"):
        parts = raw.split("\n---\n", 1)
        if len(parts) == 2:
            header, body = parts[0][4:], parts[1]
            for line in header.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                key = k.strip().lower()
                val = v.strip()
                if key == "title" and val:
                    title = val
                elif key == "summary" and val:
                    summary = val
                elif key == "tags" and val:
                    tags = [t.strip() for t in val.strip("[]").split(",") if t.strip()]

    if not summary:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                summary = stripped[:160]
                break

    links = sorted({_slugify(m.group(1)) for m in _WIKILINK_RE.finditer(body)})
    mtime = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
    return WikiPageDetail(
        slug=path.stem,
        title=title,
        scope=normalize_scope(scope),
        summary=summary,
        tags=tags,
        links=links,
        backlinks=[],
        updated_at=mtime,
        path=str(path),
        content=body.strip(),
    )


def _format_markdown_page(
    *,
    title: str,
    summary: str,
    tags: list[str],
    content: str,
) -> str:
    tag_str = ", ".join(tags)
    frontmatter = [
        "---",
        f"title: {title}",
        f"summary: {summary}",
        f"tags: [{tag_str}]",
        "---",
        "",
    ]
    return "\n".join(frontmatter) + content.strip() + "\n"


class WikiManager:
    """Manages Markdown Wiki files on disk with [[wikilinks]] and backlinks."""

    def list_pages(
        self,
        scope: str = "global",
        *,
        project_folder: Path | None = None,
    ) -> WikiPageList:
        norm = normalize_scope(scope)
        folder = _wiki_dir_for_scope(norm, project_folder)
        details: list[WikiPageDetail] = []
        for path in sorted(folder.glob("*.md")):
            try:
                details.append(_parse_markdown_page(path, norm))
            except OSError:
                continue

        backlinks_map: dict[str, set[str]] = {d.slug: set() for d in details}
        for page in details:
            for target in page.links:
                backlinks_map.setdefault(target, set()).add(page.slug)

        summaries = [
            WikiPageSummary(
                slug=d.slug,
                title=d.title,
                scope=d.scope,
                summary=d.summary,
                tags=d.tags,
                links=d.links,
                backlinks=sorted(backlinks_map.get(d.slug, set())),
                updated_at=d.updated_at,
                path=d.path,
            )
            for d in details
        ]
        summaries.sort(key=lambda item: item.updated_at, reverse=True)
        return WikiPageList(data=summaries, scope=norm)

    def get_page(
        self,
        slug: str,
        scope: str = "global",
        *,
        project_folder: Path | None = None,
    ) -> WikiPageDetail | None:
        norm = normalize_scope(scope)
        clean_slug = _slugify(slug)
        folder = _wiki_dir_for_scope(norm, project_folder)
        path = folder / f"{clean_slug}.md"
        if not path.is_file():
            return None
        detail = _parse_markdown_page(path, norm)
        all_pages = self.list_pages(norm, project_folder=project_folder).data
        for item in all_pages:
            if item.slug == clean_slug:
                detail.backlinks = item.backlinks
                break
        return detail

    def write_page(
        self,
        *,
        slug: str,
        title: str,
        content: str,
        scope: str = "global",
        summary: str | None = None,
        tags: list[str] | None = None,
        project_folder: Path | None = None,
    ) -> WikiPageDetail:
        norm = normalize_scope(scope)
        clean_slug = _slugify(slug or title)
        folder = _wiki_dir_for_scope(norm, project_folder)
        path = folder / f"{clean_slug}.md"
        auto_summary = (summary or "").strip()
        if not auto_summary:
            for line in content.splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    auto_summary = stripped[:160]
                    break
        formatted = _format_markdown_page(
            title=title.strip() or clean_slug,
            summary=auto_summary,
            tags=[str(t).strip() for t in (tags or []) if str(t).strip()],
            content=content,
        )
        path.write_text(formatted, encoding="utf-8")
        return self.get_page(clean_slug, norm, project_folder=project_folder)  # type: ignore[return-value]

    def delete_page(
        self,
        slug: str,
        scope: str = "global",
        *,
        project_folder: Path | None = None,
    ) -> bool:
        norm = normalize_scope(scope)
        clean_slug = _slugify(slug)
        folder = _wiki_dir_for_scope(norm, project_folder)
        path = folder / f"{clean_slug}.md"
        if not path.is_file():
            return False
        path.unlink(missing_ok=True)
        return True

    def build_toc_block(self, scope: str = "global", *, max_chars: int = 1800) -> str:
        pages = self.list_pages(scope).data
        if not pages:
            return ""
        lines = [f"### Living Wiki Index ({scope}) — use `wiki.read(slug)` for full text:"]
        used = len(lines[0])
        for page in pages:
            line = f"- `[[{page.slug}]]` **{page.title}**: {page.summary or 'No summary'}"
            if used + len(line) + 1 > max_chars:
                break
            lines.append(line)
            used += len(line) + 1
        return "\n".join(lines)
