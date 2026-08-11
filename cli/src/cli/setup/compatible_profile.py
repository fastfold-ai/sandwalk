"""Reusing/selecting an existing OpenAI-compatible profile during setup."""

import sys

import typer

from cli.app import console
from cli.setup.openai_endpoint import (
    _compatible_backend_display_name,
    _normalize_compatible_backend_name,
)


def _find_compatible_profile_id_by_label(cfg, label: str | None) -> str | None:
    """Find compatible profile by id/label (case-insensitive)."""
    target = str(label or "").strip().lower()
    if not target:
        return None
    profiles = cfg.openai_profiles(include_cloud=False)
    for profile_id, profile in profiles.items():
        profile_label = str(profile.get("label") or "").strip().lower()
        if target in {str(profile_id).strip().lower(), profile_label}:
            return profile_id
    return None


def _prompt_setup_compatible_profile_id(cfg) -> str | None:
    """Prompt to reuse an existing compatible profile or create new."""
    profiles = cfg.openai_profiles(include_cloud=False)
    if not profiles:
        return None

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        active_profile = cfg.get_openai_profile()
        active_backend = str((active_profile or {}).get("backend") or "").strip().lower()
        if active_backend and active_backend != "openai":
            return str((active_profile or {}).get("id") or "").strip() or None
        return None

    rows = sorted(
        profiles.items(),
        key=lambda item: str(item[1].get("label") or item[0]).strip().lower(),
    )
    active_profile_id = cfg.active_openai_profile_id()

    console.print("\n  [cyan]OpenAI-compatible profile[/cyan]")
    for idx, (profile_id, profile) in enumerate(rows, 1):
        marker = " [green]*[/green]" if profile_id == active_profile_id else ""
        backend = _normalize_compatible_backend_name(
            str(profile.get("backend") or "other").strip().lower()
        )
        backend_label = _compatible_backend_display_name(backend)
        endpoint = str(profile.get("base_url") or "").strip() or "—"
        label = str(profile.get("label") or profile_id).strip()
        console.print(
            f"    [{idx}] {label} [dim]({backend_label}, {endpoint})[/dim]{marker}"
        )
    create_idx = len(rows) + 1
    console.print(f"    [{create_idx}] Create new profile")

    default_idx = create_idx
    for idx, (profile_id, _) in enumerate(rows, 1):
        if profile_id == active_profile_id:
            default_idx = idx
            break
    try:
        raw = input(f"  Select profile [{default_idx}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    selected = raw or str(default_idx)
    if selected in {"new", "n", str(create_idx)}:
        return None
    if selected.isdigit():
        idx = int(selected)
        if 1 <= idx <= len(rows):
            return rows[idx - 1][0]
    for profile_id, profile in rows:
        label = str(profile.get("label") or "").strip().lower()
        if selected in {profile_id.lower(), label}:
            return profile_id
    console.print("  [dim]Invalid selection; creating new profile.[/dim]")
    return None
