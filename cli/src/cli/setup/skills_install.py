"""Skill-source installation helpers shared by setup and `sandwalk skills add`."""

import os
import re

from cli.app import console, spinner

_PROVIDER_BY_OWNER = {
    "fastfold-ai": "Fastfold",
    "k-dense-ai": "K-Dense-AI",
    "anthropics": "Anthropic",
    "anthropic": "Anthropic",
    "google-deepmind": "DeepMind",
    "deepmind": "DeepMind",
    "vercel-labs": "Vercel",
}


def _provider_label_for_source(source: str) -> str:
    """Return a friendly provider label for a skill source (Fastfold, Anthropic, ...)."""
    s = (source or "").strip()
    if not s:
        return "Custom"
    if s.startswith(("./", "../", "/", "~")) or os.path.exists(os.path.expanduser(s)):
        return "Local"
    owner = ""
    m = re.search(r"github\.com[:/]([\w.-]+)/", s)
    if m:
        owner = m.group(1)
    else:
        head = s.split("@", 1)[0]
        if "/" in head:
            owner = head.split("/", 1)[0]
    return _PROVIDER_BY_OWNER.get(owner.lower(), owner or "Custom")


def _skill_install_method_label(via: str) -> str:
    return {
        "git": "git",
        "archive": "GitHub download",
        "local": "local copy",
        "npx": "npx skills add",
    }.get(via, via or "?")


def _install_skill_sources(sources: list[str]) -> None:
    """Install a list of skill sources, preferring npx when available, else git.

    When npx is available, sources targeting the same repo are batched into a single
    `npx skills add <repo> --skill A --skill B ...` call (installed into the
    fastfold-owned ~/.sandwalk/.claude/skills).
    """
    from collections import OrderedDict

    from agent.skills import _npx_available, _npx_target, install_skill, npx_add

    prefer = _npx_available()
    if not prefer:
        console.print(
            f"  [dim]Installing {len(sources)} skill source(s) via `git`/GitHub download "
            "(npx not found).[/dim]"
        )
        for src in sources:
            provider = _provider_label_for_source(src)
            with spinner(f"Installing {provider} ({src})..."):
                result = install_skill(src, prefer_npx=False)
            method = _skill_install_method_label(str(result.get("via", "")))
            if result.get("ok"):
                console.print(
                    f"  [green]\u2713[/green] [cyan]{provider}[/cyan]: {result['summary']} "
                    f"[dim](method: {method})[/dim]"
                )
            else:
                console.print(
                    f"  [red]\u2717[/red] [cyan]{provider}[/cyan] {src}: "
                    f"{result.get('summary', 'install failed')} [dim](method: {method})[/dim]"
                )
        return

    console.print(
        f"  [dim]Installing {len(sources)} skill source(s) via `npx skills add` "
        "(grouped per repo; git fallback)...[/dim]"
    )
    # Group GitHub sources by npx target repo; keep local paths separate (git/local).
    groups: OrderedDict[str, dict] = OrderedDict()
    fallback: list[str] = []
    for src in sources:
        s = src.strip()
        if s.startswith(("./", "../", "/", "~")) or os.path.exists(os.path.expanduser(s)):
            fallback.append(src)
            continue
        target, skill, whole = _npx_target(src)
        g = groups.setdefault(target, {"skills": [], "whole": False, "provider": _provider_label_for_source(src)})
        if whole:
            g["whole"] = True
        elif skill and skill not in g["skills"]:
            g["skills"].append(skill)

    for target, g in groups.items():
        provider = g["provider"]
        with spinner(f"Installing {provider} ({target})..."):
            result = npx_add(target, g["skills"] or None, g["whole"])
        if result.get("ok"):
            console.print(f"  [green]\u2713[/green] [cyan]{provider}[/cyan]: {result['summary']} [dim](method: npx skills add)[/dim]")
        else:
            # Fall back to git for this repo's sources.
            console.print(f"  [yellow]npx failed for {target}; trying git...[/yellow] [dim]{result.get('summary','')}[/dim]")
            git_src = target if g["whole"] else f"{target}@skills/{g['skills'][0]}" if g["skills"] else target
            with spinner(f"Installing {provider} ({git_src}) via git..."):
                gres = install_skill(git_src, prefer_npx=False)
            style = "green" if gres.get("ok") else "red"
            mark = "\u2713" if gres.get("ok") else "\u2717"
            method = _skill_install_method_label(str(gres.get("via", "")))
            console.print(
                f"  [{style}]{mark}[/{style}] [cyan]{provider}[/cyan]: "
                f"{gres.get('summary','')} [dim](method: {method})[/dim]"
            )

    for src in fallback:
        provider = _provider_label_for_source(src)
        with spinner(f"Installing {provider} ({src})..."):
            result = install_skill(src, prefer_npx=False)
        method = _skill_install_method_label(str(result.get("via", "")))
        style = "green" if result.get("ok") else "red"
        mark = "\u2713" if result.get("ok") else "\u2717"
        console.print(f"  [{style}]{mark}[/{style}] [cyan]{provider}[/cyan]: {result.get('summary','')} [dim](method: {method})[/dim]")
