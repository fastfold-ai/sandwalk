"""
Fastfold Agent CLI entry point.

Usage:
    fastfold                              # Interactive mode
    fastfold "your question"              # Single query
    fastfold --smiles "CCO" "Profile"     # With compound context
    fastfold config set key value         # Configuration
    fastfold data pull depmap             # Data management
"""

import os
import json
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import quote, urlparse
from uuid import uuid4
import typer
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone
from typer.models import OptionInfo
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from _version import __version__
from agent.session import Session
from ui.terminal import InteractiveTerminal, SLASH_COMMANDS


# ─── Startup banner ─────────────────────────────────────────
BANNER = """
[bold #2D7BEA]     ▃▃[/]
[bold #2D7BEA]    ▃▃▃▃[/]
[bold #25C19F]  ▅▅ ▃▃▃[/]
[bold #25C19F] ▅▅▅▅▅[/]
[bold #F5A623]  ▅▅▅ ▆▆[/]
[bold #F5A623]    ▆▆▆▆▆[/]
[bold #D4148E]   ▃ ▆▆▆▆[/]
[bold #D4148E]  ▃▃▃ ▆[/]
[bold #D4148E]   ▃▃▃[/]
"""

app = typer.Typer(
    name="fastfold",
    help=(
        "Fastfold Agent CLI — Where scientists and AI agents work together doing real science.\n\n"
        "Common usage:\n"
        '  fastfold "your research question"\n'
        '  fastfold --smiles "CCO" "Profile this compound"\n'
        "  fastfold config show\n"
        "  fastfold tool list"
    ),
    no_args_is_help=False,
)
console = Console()


from contextlib import contextmanager


@contextmanager
def spinner(message: str, *, console: Console = console):
    """Animated status spinner for long-running operations.

    Renders an animated 'dots' spinner on a TTY; on a non-interactive stream
    Rich falls back to a single static line, so this is always safe to use.
    """
    with console.status(f"[green]{message}[/green]", spinner="dots"):
        yield


FASTFOLD_CLOUD_API_KEYS_URL = "https://cloud.fastfold.ai/api-keys"
BOLTZ_API_KEYS_URL = "https://api.boltz.bio/console"
BOLTZ_SKILL_SOURCE = "fastfold-ai/skills@skills/boltz"
BOLTZ_INSTALL_SCRIPT = "set -euo pipefail; curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
SETUP_PROVIDER_ORDER = (
    "anthropic",
    "openai",
    "xai",
    "google",
    "nvidia",
    "opencode",
    "openai_compatible",
)
UV_INSTALL_FLAVORS = frozenset({"all", "win_build"})
UV_UPGRADE_PYTHON_VERSION = "3.11"
PYPI_PROJECT_JSON_URL = "https://pypi.org/pypi/fastfold-agent-cli/json"
_SEMVER_TRIPLET_PATTERN = re.compile(r"^\s*v?(\d+)\.(\d+)\.(\d+)")
_UPGRADE_CACHE_PATH = Path.home() / ".fastfold-cli" / "cache" / "upgrade-version.json"
_UPGRADE_CACHE_MAX_AGE_S = 60 * 60 * 6
_BANNER_TOOL_COUNT_HINT = 192


def _installed_claude_skill_names() -> list[str]:
    """Return installed skill names across all tiers (global, project, bundled)."""
    from agent.skills import installed_skill_names

    return installed_skill_names()


def _count_installed_claude_skills() -> int:
    """Count installed agent skills."""
    return len(_installed_claude_skill_names())


def _resolve_fastfold_subscription_tier(cfg) -> str:
    """Resolve Fastfold subscription tier from API, with local fallback."""
    fallback_raw = str(
        os.environ.get("FASTFOLD_SUBSCRIPTION_TIER")
        or cfg.get("fastfold.subscription_tier", "")
        or ""
    ).strip().lower()

    def _normalize_plan_code(raw: str) -> str:
        value = str(raw or "").strip().lower()
        if value in {"pro+", "pro-plus", "pro plus"}:
            return "pro_plus"
        return value

    def _plan_rank(plan_code: str) -> int:
        ranks = {
            "free": 0,
            "pro": 1,
            "pro_plus": 2,
            "ultra": 3,
        }
        return ranks.get(plan_code, -1)

    fallback = _normalize_plan_code(fallback_raw)
    if _plan_rank(fallback) < 0:
        fallback = ""

    api_key = str(
        os.environ.get("FASTFOLD_API_KEY")
        or cfg.get("api.fastfold_cloud_key")
        or ""
    ).strip()
    if not api_key:
        return fallback

    base_url = (
        os.environ.get("FASTFOLD_API_BASE_URL", "https://api.fastfold.ai").strip()
        or "https://api.fastfold.ai"
    )
    url = f"{base_url.rstrip('/')}/v1/billing/workspaces/plans"
    req = urllib.request.Request(
        url=url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "X-API-Key": api_key,
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        # Billing endpoints are currently cookie-auth only. For API-key callers,
        # avoid showing a misleading default plan when backend returns 401.
        if exc.code == 401:
            return fallback
        return fallback
    except (urllib.error.URLError, TimeoutError):
        return fallback

    try:
        payload = json.loads(text) if text else {}
    except Exception:
        return fallback
    if not isinstance(payload, dict):
        return fallback

    items = payload.get("items")
    if not isinstance(items, list):
        return fallback

    best_plan = None
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_plan = _normalize_plan_code(str(item.get("plan_code") or ""))
        if not raw_plan:
            continue
        if best_plan is None or _plan_rank(raw_plan) > _plan_rank(best_plan):
            best_plan = raw_plan

    resolved = best_plan or fallback
    return resolved if _plan_rank(resolved) >= 0 else fallback


def _format_plan_label(plan_code: str) -> str:
    """Convert normalized plan code to friendly display label."""
    normalized = str(plan_code or "").strip().lower()
    if normalized == "pro_plus":
        return "Pro+"
    if not normalized:
        return ""
    return normalized.replace("_", " ").title()


def _random_command_tip_markup() -> str:
    """Return a random slash-command tip from actual terminal commands."""
    if not SLASH_COMMANDS:
        return "[dim]Tip: use slash commands in interactive mode.[/dim]"

    command, description = random.choice(list(SLASH_COMMANDS.items()))
    return f"[dim]Tip: try [/][bold #D4148E]{command}[/][dim] — {description}[/dim]"


_BOLTZ_NEWS_USE_CASES = (
    "structure and binding",
    "protein design",
    "protein screening",
    "small-molecule design",
    "small-molecule screening",
    "ADME prediction",
)


def _random_news_item_markup() -> str:
    """Return a rotating Boltz API news/action line."""
    installed = set(_installed_claude_skill_names())
    use_case = random.choice(_BOLTZ_NEWS_USE_CASES)
    if "boltz" in installed:
        return (
            "[bold #25C19F]Boltz API skill now available![/] "
            f"[#7A7A7A]· Try: Show me Boltz API examples for {use_case}[/]"
        )
    return (
        "[bold #25C19F]Boltz API skill now available[/] "
        f"[#7A7A7A]· Try: Show me Boltz API examples for {use_case}[/]"
    )


def _normalize_upgrade_flavor(value: object) -> Optional[str]:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in UV_INSTALL_FLAVORS else None


def _default_upgrade_flavor() -> str:
    return "win_build" if os.name == "nt" else "all"


def resolve_upgrade_flavor(cfg=None, persist: bool = True) -> str:
    """Resolve uv install flavor from config, with OS fallback."""
    if cfg is None:
        from agent.config import Config
        cfg = Config.load()

    configured = _normalize_upgrade_flavor(cfg.get("install.uv_flavor"))
    if configured:
        return configured

    fallback = _default_upgrade_flavor()
    if persist:
        try:
            cfg.set("install.uv_flavor", fallback)
            cfg.save()
        except Exception:
            # Upgrade flow should still continue even if config write fails.
            pass
    return fallback


def build_upgrade_command(flavor: str) -> list[str]:
    normalized = _normalize_upgrade_flavor(flavor) or _default_upgrade_flavor()
    package_ref = f"fastfold-agent-cli[{normalized}]"
    return ["uv", "tool", "install", package_ref, "--python", UV_UPGRADE_PYTHON_VERSION, "--upgrade"]


def _parse_semver_triplet(version: str) -> Optional[tuple[int, int, int]]:
    match = _SEMVER_TRIPLET_PATTERN.match(str(version or "").strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def is_newer_version(latest: str, current: str) -> bool:
    latest_triplet = _parse_semver_triplet(latest)
    current_triplet = _parse_semver_triplet(current)
    if not latest_triplet or not current_triplet:
        return False
    return latest_triplet > current_triplet


def fetch_pypi_latest_version(timeout_s: float = 2.5) -> Optional[str]:
    req = urllib.request.Request(
        url=PYPI_PROJECT_JSON_URL,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None

    try:
        payload = json.loads(text) if text else {}
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None
    info = payload.get("info")
    if not isinstance(info, dict):
        return None
    version = str(info.get("version") or "").strip()
    return version or None


def get_upgrade_available_version(current_version: str = __version__) -> Optional[str]:
    latest = fetch_pypi_latest_version()
    if not latest:
        return None
    return latest if is_newer_version(latest, current_version) else None


def _get_cached_upgrade_available_version(current_version: str = __version__) -> Optional[str]:
    """Return cached upgrade notice if fresh; never performs network I/O."""
    try:
        if not _UPGRADE_CACHE_PATH.exists():
            return None
        payload = json.loads(_UPGRADE_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    checked_at = float(payload.get("checked_at") or 0)
    if checked_at <= 0 or (time.time() - checked_at) > _UPGRADE_CACHE_MAX_AGE_S:
        return None
    latest = str(payload.get("latest") or "").strip()
    if not latest:
        return None
    return latest if is_newer_version(latest, current_version) else None


def _write_upgrade_cache(latest: Optional[str]) -> None:
    """Persist latest seen PyPI version for non-blocking future boots."""
    try:
        _UPGRADE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _UPGRADE_CACHE_PATH.write_text(
            json.dumps(
                {
                    "latest": str(latest or "").strip(),
                    "checked_at": time.time(),
                }
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _normalize_share_id(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("share_id is required")
    if "/agents/share/" in raw:
        suffix = raw.split("/agents/share/", 1)[1]
        raw = suffix.split("?", 1)[0].split("#", 1)[0].strip()
    return raw


def _parse_unix_timestamp(value: object) -> float:
    text = str(value or "").strip()
    if not text:
        return time.time()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except Exception:
        return time.time()


def _resolve_agents_api_base_url(cli_value: Optional[str] = None) -> str:
    candidate = str(cli_value or os.environ.get("FASTFOLD_AGENTS_API_URL") or "").strip()
    if candidate:
        return candidate.rstrip("/")
    return "https://agents-api.fastfold.ai/v1"


def _agents_api_request_json(
    base_url: str,
    path: str,
    *,
    headers: dict[str, str],
    method: str = "GET",
    timeout: float = 20.0,
    body: dict | None = None,
) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    data: bytes | None = None
    normalized_method = str(method or "GET").upper()
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url=url, headers=request_headers, method=normalized_method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Agents API {exc.code} for {path}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Agents API at {url}: {exc}") from exc

    try:
        payload = json.loads(body) if body else {}
    except Exception as exc:
        raise RuntimeError(f"Agents API returned invalid JSON for {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Agents API returned unexpected response for {path}")
    return payload


def _agents_api_get_json(base_url: str, path: str, *, headers: dict[str, str], timeout: float = 20.0) -> dict:
    return _agents_api_request_json(base_url, path, headers=headers, method="GET", timeout=timeout)


def _safe_workspace_relative_path(raw_path: str) -> Optional[Path]:
    normalized = str(raw_path or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return None
    parts = [segment for segment in normalized.split("/") if segment and segment != "."]
    if any(segment == ".." for segment in parts):
        return None
    if not parts:
        return None
    return Path(*parts)


def _download_binary(url: str, *, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to download shared file from {url}: {exc}") from exc


def _start_upgrade_check_refresh() -> None:
    """Refresh cached PyPI latest version in a daemon thread."""
    import threading

    def _worker():
        latest = fetch_pypi_latest_version()
        _write_upgrade_cache(latest)

    try:
        threading.Thread(target=_worker, daemon=True).start()
    except Exception:
        pass


def _resolve_fastfold_subscription_tier_local(cfg) -> str:
    """Resolve tier from local/env hints only (no network)."""
    raw = str(
        os.environ.get("FASTFOLD_SUBSCRIPTION_TIER")
        or cfg.get("fastfold.subscription_tier", "")
        or ""
    ).strip().lower()
    if raw in {"pro+", "pro-plus", "pro plus"}:
        return "pro_plus"
    return raw


def _get_loaded_tool_count_hint() -> int:
    """Return loaded tool count when already available, else a static hint."""
    try:
        from tools import registry

        count = len(registry.list_tools())
        if count > 0:
            return count
    except Exception:
        pass
    return _BANNER_TOOL_COUNT_HINT


def _get_cached_skills_update_safe() -> Optional[dict]:
    """Local-only cached skills-update check for the banner (never raises)."""
    try:
        from agent.skills import get_cached_skills_update

        return get_cached_skills_update()
    except Exception:
        return None


def _start_skills_update_check() -> None:
    """Refresh the skills-update cache in a daemon thread (no boot-path network)."""
    import threading

    def _worker():
        try:
            from agent.skills import refresh_skills_update_cache

            refresh_skills_update_cache()
        except Exception:
            pass

    try:
        threading.Thread(target=_worker, daemon=True).start()
    except Exception:
        pass


_FASTFOLD_CORE_SKILL_NAMES = {
    "boltz",
    "fold",
    "protein_design_boltzgen",
    "md_openmm_calvados",
    "md_openmmdl",
    "slack_report",
}


def _has_fastfold_skills_installed() -> bool:
    """Return True when at least one official Fastfold skill is installed."""
    from agent.skills import user_installed_skill_names

    installed = set(user_installed_skill_names())
    return bool(installed.intersection(_FASTFOLD_CORE_SKILL_NAMES))


def _maybe_offer_fastfold_skills_install_after_upgrade(
    *,
    ui: Console,
    install_missing: bool = False,
    prompt_if_missing: bool = True,
) -> None:
    """Offer to install official Fastfold skills after a successful upgrade."""
    if _has_fastfold_skills_installed():
        return

    if install_missing:
        ui.print("\n[cyan]Installing official Fastfold skills...[/cyan]")
        _install_skill_sources(["fastfold-ai/skills"])
        return

    if not prompt_if_missing:
        return

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        ui.print(
            "\n  [dim]No official Fastfold skills detected. "
            "Install them with `fastfold skills add fastfold-ai/skills`.[/dim]"
        )
        return

    try:
        answer = input(
            "\n  Install official Fastfold skills now? [Y/n] "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        ui.print("\n  [dim]Skipped Fastfold skills install.[/dim]")
        return

    if answer in {"n", "no"}:
        ui.print(
            "  [dim]Skipped. Add later with "
            "`fastfold skills add fastfold-ai/skills`.[/dim]"
        )
        return

    ui.print("  [cyan]Installing official Fastfold skills...[/cyan]")
    _install_skill_sources(["fastfold-ai/skills"])


def execute_upgrade(
    console_obj: Optional[Console] = None,
    cfg=None,
    *,
    install_missing_skills: bool = False,
    prompt_missing_skills: bool = True,
) -> bool:
    """Run uv tool upgrade with persisted (or fallback) install flavor."""
    ui = console_obj or console
    flavor = resolve_upgrade_flavor(cfg=cfg, persist=True)
    cmd = build_upgrade_command(flavor)
    ui.print("\n[bold cyan]Upgrading fastfold-agent-cli[/bold cyan]")
    ui.print(f"[dim]Flavor:[/dim] {flavor}")
    ui.print(f"[dim]$ {' '.join(cmd)}[/dim]")

    try:
        with spinner("Upgrading via uv (this may take a moment)...", console=ui):
            proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        ui.print("[red]`uv` command not found. Install uv first: https://docs.astral.sh/uv/[/red]")
        return False
    except Exception as exc:
        ui.print(f"[red]Upgrade failed to start:[/red] {exc}")
        return False

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if stdout:
        ui.print(stdout)
    if stderr:
        ui.print(stderr, style="yellow" if proc.returncode == 0 else "red")

    if proc.returncode != 0:
        ui.print(f"[red]Upgrade failed[/red] (exit={proc.returncode}).")
        return False

    ui.print("[green]Upgrade complete.[/green] Restart `fastfold` to use the new version.")
    _maybe_offer_fastfold_skills_install_after_upgrade(
        ui=ui,
        install_missing=install_missing_skills,
        prompt_if_missing=prompt_missing_skills,
    )
    ui.print("[cyan]Running skills-upgrade...[/cyan]")
    try:
        from agent.skills import upgrade_skills, GLOBAL_SKILLS_DIR

        with ui.status("[green]Syncing agent skills...[/green]", spinner="dots") as status:
            result = upgrade_skills(
                include_catalog=True,
                include_npx=True,
                progress=lambda msg: status.update(f"[green]{msg}[/green]"),
            )
    except Exception as exc:
        ui.print(f"[yellow]skills-upgrade failed:[/yellow] {exc}")
        return True

    if result["added"]:
        ui.print(f"  [green]Added:[/green] {', '.join(result['added'])}")
    if result["updated"]:
        ui.print(f"  [green]Updated:[/green] {', '.join(result['updated'])}")
    if result.get("npx_synced"):
        ui.print(
            f"  [green]npx-synced:[/green] {result['npx_synced']} project-local source(s)"
        )
    if result["failed"]:
        for source, reason in result["failed"]:
            ui.print(f"  [yellow]Failed:[/yellow] {source} — {reason}")
    ui.print(f"  [dim]{result['summary']}[/dim]")
    ui.print(f"  [dim]Location: {GLOBAL_SKILLS_DIR}[/dim]")
    return True


# ─── Config subcommand ────────────────────────────────────────

config_app = typer.Typer(help="Manage fastfold configuration")
app.add_typer(config_app, name="config")

agent_app = typer.Typer(help="Fork and import shared cloud sessions")
app.add_typer(agent_app, name="agent")


@config_app.command("set")
def config_set(key: str, value: str):
    """Set a configuration value."""
    from agent.config import Config

    cfg = Config.load()
    try:
        cfg.set(key, value)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2)
    cfg.save()
    if key == "agent.profile":
        console.print(
            f"  [green]Set[/green] {key} = {cfg.get('agent.profile')} (applied preset settings)"
        )
    else:
        console.print(f"  [green]Set[/green] {key} = {value}")


@config_app.command("unset")
def config_unset(key: str):
    """Unset a configuration value (revert to default/env fallback)."""
    from agent.config import Config

    cfg = Config.load()
    cfg.unset(key)
    cfg.save()
    console.print(f"  [green]Unset[/green] {key}")


@config_app.command("get")
def config_get(key: str):
    """Get a configuration value."""
    from agent.config import Config

    cfg = Config.load()
    val = cfg.get(key)
    console.print(f"  {key} = {val}")


@config_app.command("show")
def config_show():
    """Show all configuration."""
    from agent.config import Config

    cfg = Config.load()
    console.print(cfg.to_table())


@config_app.command("validate")
def config_validate():
    """Validate configuration and report issues."""
    from agent.config import Config

    cfg = Config.load()
    issues = cfg.validate()
    if not issues:
        console.print("[green]Configuration is valid. No issues found.[/green]")
        return
    console.print(f"[yellow]Found {len(issues)} issue(s):[/yellow]")
    for issue in issues:
        console.print(f"  - {issue}")
    raise typer.Exit(code=2)


# ─── Keys command ────────────────────────────────────────────


@app.command("keys")
def keys_cmd():
    """Show status of optional API keys and what they unlock."""
    from agent.config import Config

    cfg = Config.load()
    console.print(cfg.keys_table())


# ─── MCP subcommand ──────────────────────────────────────────

mcp_app = typer.Typer(
    help="List and manage MCP servers (catalog defaults + custom)",
    invoke_without_command=True,
)
app.add_typer(mcp_app, name="mcp")


@mcp_app.callback(invoke_without_command=True)
def mcp_root(ctx: typer.Context):
    """Show MCP status (same as `fastfold mcp list`)."""
    if ctx.invoked_subcommand is not None:
        return
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["list"], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("list")
def mcp_list_cmd():
    """List suggested catalog + registered MCP servers."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["list"], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("catalog")
def mcp_catalog_cmd():
    """Show suggested cloud MCP defaults."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["catalog"], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("connect")
def mcp_connect_cmd(
    catalog_id: str = typer.Argument(..., help="Catalog id (tamarind|latch|neurosnap|linear)"),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="API key (required for neurosnap/tamarind; optional for linear)",
        hide_input=True,
    ),
):
    """Connect a suggested MCP (API key or OAuth browser URL)."""
    from agent.mcp_manage import handle_mcp_argv

    argv = ["connect", catalog_id]
    if api_key:
        argv.extend(["--api-key", api_key])
    code = handle_mcp_argv(argv, console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("disconnect")
def mcp_disconnect_cmd(
    catalog_id: str = typer.Argument(..., help="Catalog id to disconnect"),
):
    """Clear credentials and disable a catalog MCP."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["disconnect", catalog_id], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("enable")
def mcp_enable_cmd(ref: str = typer.Argument(..., help="Catalog id, server id, or name")):
    """Enable a registered MCP server."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["enable", ref], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("disable")
def mcp_disable_cmd(ref: str = typer.Argument(..., help="Catalog id, server id, or name")):
    """Disable a registered MCP server."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["disable", ref], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("validate")
def mcp_validate_cmd(ref: str = typer.Argument(..., help="Catalog id, server id, or name")):
    """Probe MCP initialize + tools/list."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["validate", ref], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("tools")
def mcp_tools_cmd(ref: str = typer.Argument(..., help="Catalog id, server id, or name")):
    """List tools from an MCP server (same as validate)."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["tools", ref], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("add")
def mcp_add_cmd(
    name: str = typer.Argument(..., help="Server display name"),
    url: Optional[str] = typer.Option(None, "--url", help="Remote MCP URL"),
    command: Optional[str] = typer.Option(None, "--command", help="stdio command"),
    arg: list[str] = typer.Option(None, "--arg", help="stdio arg (repeatable)"),
    transport: str = typer.Option(
        "http",
        "--transport",
        help="http|sse|stdio (http = streamable_http)",
    ),
):
    """Add a custom MCP server."""
    from agent.mcp_manage import handle_mcp_argv

    argv = ["add", name, "--transport", transport]
    if url:
        argv.extend(["--url", url])
    if command:
        argv.extend(["--command", command])
    for value in arg or []:
        argv.extend(["--arg", value])
    code = handle_mcp_argv(argv, console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("remove")
def mcp_remove_cmd(ref: str = typer.Argument(..., help="Catalog id, server id, or name")):
    """Remove a registered MCP server."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["remove", ref], console)
    if code:
        raise typer.Exit(code=code)


@app.command("serve")
def serve_cmd(
    host: str = typer.Option("127.0.0.1", "--host", help="HTTP bind address"),
    port: int = typer.Option(8787, "--port", min=1, max=65535, help="HTTP bind port"),
    public: bool = typer.Option(
        False,
        "--public",
        help="Allow a non-loopback listener; requires API key, origins, and hosts",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar="FASTFOLD_SERVER_API_KEY",
        help="Backend bearer token (or FASTFOLD_SERVER_API_KEY)",
        hide_input=True,
    ),
    allowed_origin: list[str] = typer.Option(
        None,
        "--allowed-origin",
        help="Allowed browser origin; repeat for multiple origins",
    ),
    allowed_host: list[str] = typer.Option(
        None,
        "--allowed-host",
        help="Allowed Host header; repeat for multiple hosts",
    ),
    uds: Optional[Path] = typer.Option(
        None,
        "--uds",
        help="Serve over a user-scoped Unix domain socket instead of TCP",
    ),
):
    """Start the local or explicitly exposed FastFold agent server."""
    from agent_server.main import run_server

    try:
        run_server(
            host=host,
            port=port,
            public=public,
            api_key=api_key,
            allowed_origins=allowed_origin,
            allowed_hosts=allowed_host,
            uds=uds,
        )
    except ValueError as exc:
        console.print(f"[red]Server configuration error:[/red] {exc}")
        raise typer.Exit(code=2) from exc


@app.command("sync")
def sync_cmd(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Re-import sessions even if they already exist in the shared database",
    ),
):
    """Import legacy CLI JSONL sessions into the shared SQLite store for the UI."""
    from agent_server.session_sync import sync_jsonl_sessions

    console.print(
        "  [cyan]Syncing legacy CLI sessions into the shared UI database…[/cyan]"
        + (" [dim](force)[/dim]" if force else "")
    )
    result = sync_jsonl_sessions(force=force)
    console.print(
        "  [green]Sync complete.[/green] "
        f"scanned={result.scanned} imported={result.imported} "
        f"updated={result.updated} skipped={result.skipped} failed={result.failed}"
    )
    if result.failed and result.details:
        for line in result.details:
            if "failed" in line:
                console.print(f"  [yellow]{line}[/yellow]")
    if result.imported or result.updated:
        console.print(
            "  [dim]Run `fastfold serve` and open the local UI to continue these chats.[/dim]"
        )


@app.command("upgrade")
def upgrade_cmd(
    install_skills: bool = typer.Option(
        False,
        "--install-skills",
        help="Auto-install official Fastfold skills if missing",
    ),
    skip_skills_prompt: bool = typer.Option(
        False,
        "--skip-skills-prompt",
        help="Skip the post-upgrade Fastfold skills prompt",
    ),
):
    """Upgrade fastfold-agent-cli with uv tool install --upgrade."""
    from agent.config import Config

    cfg = Config.load()
    ok = execute_upgrade(
        console_obj=console,
        cfg=cfg,
        install_missing_skills=install_skills,
        prompt_missing_skills=not skip_skills_prompt,
    )
    if not ok:
        raise typer.Exit(code=1)


@agent_app.command("fork")
def agent_fork_cmd(
    share_id: str = typer.Argument(..., help="Shared chat ID or full /agents/share/<id> URL"),
    agents_api_url: Optional[str] = typer.Option(
        None,
        "--agents-api-url",
        envvar="FASTFOLD_AGENTS_API_URL",
        help="Agents API base URL (defaults to FASTFOLD_AGENTS_API_URL or https://agents-api.fastfold.ai/v1)",
    ),
    fastfold_api_key: Optional[str] = typer.Option(
        None,
        "--fastfold-api-key",
        envvar="FASTFOLD_API_KEY",
        help="Optional Fastfold Cloud API key (required for restricted-email shared chats)",
    ),
    include_files: bool = typer.Option(
        True,
        "--include-files/--no-files",
        help="Download shared files into local sandbox.output_dir/shared_forks/<share_id>",
    ),
):
    """Fork a shared cloud chat into a local Fastfold Agent CLI session."""
    from agent.config import Config
    from agent.trajectory import Trajectory, Turn

    try:
        cfg = Config.load()
        resolved_share_id = _normalize_share_id(share_id)
        base_url = _resolve_agents_api_base_url(agents_api_url)
        resolved_key = (
            str(fastfold_api_key or "").strip()
            or str(os.environ.get("FASTFOLD_API_KEY") or "").strip()
            or str(cfg.get("api.fastfold_cloud_key") or "").strip()
        )

        headers = {
            "Accept": "application/json",
            "User-Agent": f"fastfold-agent-cli/{__version__}",
        }
        if resolved_key:
            headers["X-Fastfold-Api-Key"] = resolved_key

        encoded_share_id = quote(resolved_share_id, safe="")
        with spinner("Fetching shared session metadata..."):
            bootstrap = _agents_api_get_json(base_url, f"/shares/{encoded_share_id}", headers=headers)
            history = _agents_api_get_json(base_url, f"/shares/{encoded_share_id}/history", headers=headers)
        thread = bootstrap.get("thread") if isinstance(bootstrap.get("thread"), dict) else {}
        title = str(thread.get("title") or "Imported shared session").strip()
        messages = history.get("messages") if isinstance(history.get("messages"), list) else []

        with spinner("Reconstructing local session trajectory..."):
            turns: list[Turn] = []
            pending_query = ""
            pending_query_ts: float | None = None
            assistant_parts: list[str] = []
            for message in messages:
                if not isinstance(message, dict):
                    continue
                role = str(message.get("role") or "").strip().lower()
                content = str(message.get("content") or "").strip()
                created_at = _parse_unix_timestamp(message.get("created_at"))
                if role == "user":
                    if pending_query:
                        turns.append(
                            Turn(
                                query=pending_query,
                                answer="\n\n".join(assistant_parts).strip(),
                                timestamp=pending_query_ts or created_at,
                            )
                        )
                    pending_query = content
                    pending_query_ts = created_at
                    assistant_parts = []
                    continue
                if role == "assistant" and pending_query and content:
                    assistant_parts.append(content)
            if pending_query:
                turns.append(
                    Turn(
                        query=pending_query,
                        answer="\n\n".join(assistant_parts).strip(),
                        timestamp=pending_query_ts or time.time(),
                    )
                )

            session_id = str(uuid4())[:8]
            trajectory = Trajectory(session_id=session_id, title=title)
            trajectory.turns = turns
            if turns:
                trajectory.created_at = turns[0].timestamp
                trajectory.updated_at = turns[-1].timestamp
            trajectory.model = str(
                (thread.get("metadata") or {}).get("inspect_base_model_key")
                if isinstance(thread.get("metadata"), dict)
                else ""
            ).strip() or "cloud-shared-session"
            trajectory.usage_data = {
                "imported_from_share_id": resolved_share_id,
                "imported_from_thread_id": str(thread.get("id") or "").strip(),
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "messages_count": len(messages),
                "turns_count": len(turns),
            }
            trajectory.save()

        share_files_count = 0
        share_folders_count = 0
        restored_files = 0
        restored_root: Path | None = None
        fork_count: int | None = None
        if include_files:
            with spinner("Loading shared file manifest..."):
                files_payload = _agents_api_get_json(base_url, f"/shares/{encoded_share_id}/files", headers=headers)
            listed_files = files_payload.get("data") if isinstance(files_payload.get("data"), list) else []
            share_files_count = len(listed_files)
            unique_parent_dirs: set[str] = set()
            output_root = Path(str(cfg.get("sandbox.output_dir") or Path.cwd() / "outputs")).expanduser().resolve()
            restored_root = output_root / "shared_forks" / resolved_share_id
            with spinner(f"Downloading {share_files_count} shared files..."):
                for row in listed_files:
                    if not isinstance(row, dict):
                        continue
                    rel_path = _safe_workspace_relative_path(str(row.get("path") or ""))
                    if rel_path is None:
                        continue
                    parent = str(rel_path.parent).strip()
                    if parent and parent != ".":
                        unique_parent_dirs.add(parent)
                    encoded_path = quote(str(rel_path).replace("\\", "/"), safe="")
                    download_payload = _agents_api_get_json(
                        base_url,
                        f"/shares/{encoded_share_id}/files/download?path={encoded_path}",
                        headers=headers,
                    )
                    signed_url = str(download_payload.get("url") or "").strip()
                    if not signed_url:
                        continue
                    content = _download_binary(signed_url)
                    target_path = restored_root / rel_path
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    target_path.write_bytes(content)
                    restored_files += 1
            share_folders_count = len(unique_parent_dirs)

            # Mirror restored files into the canonical per-session workspace so
            # the local Agents UI file tree can list them after sync/resume.
            try:
                import shutil

                from agent.config import CONFIG_DIR

                workspace_root = (CONFIG_DIR / "workspaces" / session_id).resolve()
                workspace_root.mkdir(parents=True, exist_ok=True)
                for child in restored_root.iterdir():
                    destination = workspace_root / child.name
                    if child.is_dir():
                        shutil.copytree(child, destination, dirs_exist_ok=True)
                    else:
                        shutil.copy2(child, destination)
                console.print(f"  [dim]Session workspace:[/dim] {workspace_root}")
            except Exception:
                pass

        # Best-effort analytics so public and local CLI forks are reflected in
        # shared-page fork counts (same metric surface as cloud forks).
        try:
            tracked = _agents_api_request_json(
                base_url,
                f"/shares/{encoded_share_id}/fork/local",
                headers=headers,
                method="POST",
                timeout=12.0,
            )
            raw_count = tracked.get("fork_count")
            if raw_count is not None:
                fork_count = max(0, int(raw_count))
        except Exception:
            fork_count = None

        console.print("[green]Imported shared session locally.[/green]")
        console.print(f"  [dim]Share ID:[/dim] {resolved_share_id}")
        console.print(f"  [dim]Session ID:[/dim] {session_id}")
        console.print(f"  [dim]Session file:[/dim] {Trajectory.session_path(session_id)}")
        console.print(f"  [dim]Messages imported:[/dim] {len(messages)}")
        if include_files and restored_root is not None:
            console.print(f"  [dim]Shared files:[/dim] {share_files_count}")
            console.print(f"  [dim]Shared folders:[/dim] {share_folders_count}")
            console.print(f"  [dim]Files restored:[/dim] {restored_files}")
            console.print(f"  [dim]Restore location:[/dim] {restored_root}")
        else:
            console.print("  [dim]File import:[/dim] skipped (--no-files)")
        if fork_count is not None:
            console.print(f"  [dim]Fork count:[/dim] {fork_count}")
        console.print(f"  [cyan]Resume this session:[/cyan] fastfold --resume {session_id}")
    except RuntimeError as exc:
        message = str(exc)
        if " 404 " in f" {message} " and "/shares/" in message:
            console.print(
                "[red]Shared session not found.[/red]\n"
                "  Check the share ID or URL, and ensure the link still exists."
            )
            raise typer.Exit(code=2)
        if " 401 " in f" {message} " or " 403 " in f" {message} ":
            console.print(
                "[red]Access denied for this shared session.[/red]\n"
                "  This share may be restricted by email. Set FASTFOLD_API_KEY "
                "from an allowed account and retry."
            )
            raise typer.Exit(code=2)
        console.print(f"[red]Could not fork shared session.[/red]\n  {message}")
        raise typer.Exit(code=2)
    except ValueError as exc:
        console.print(f"[red]Invalid input:[/red] {exc}")
        raise typer.Exit(code=2)


@app.command("setup")
def setup_cmd(
    api_key: Optional[str] = typer.Option(
        None, "--api-key", help="Anthropic API key (non-interactive mode)"
    ),
    openai_api_key: Optional[str] = typer.Option(
        None, "--openai-api-key", help="OpenAI API key (non-interactive mode)"
    ),
    openai_base_url: Optional[str] = typer.Option(
        None,
        "--openai-base-url",
        help="OpenAI-compatible base URL (e.g. http://localhost:11434/v1)",
    ),
    openai_compatible_backend: Optional[str] = typer.Option(
        None,
        "--openai-compatible-backend",
        help="Compatible backend type: ollama, unsloth, omlx, ds4, llama_cpp, lm_studio, or other",
    ),
    profile_label: Optional[str] = typer.Option(
        None,
        "--profile-label",
        help="Label for the OpenAI-compatible profile to create/update",
    ),
    profile_template: Optional[str] = typer.Option(
        None,
        "--profile-template",
        help="OpenAI-compatible template: ollama, unsloth, omlx, ds4, llama_cpp, lm_studio, or other",
    ),
    profile_endpoint: Optional[str] = typer.Option(
        None,
        "--profile-endpoint",
        help="Profile endpoint URL (alias of --openai-base-url for compatible setup)",
    ),
    profile_key: Optional[str] = typer.Option(
        None,
        "--profile-key",
        help="API key for the selected OpenAI-compatible profile",
    ),
    profile_default_model: Optional[str] = typer.Option(
        None,
        "--profile-default-model",
        help="Default model id to store in the selected compatible profile",
    ),
    set_default_profile: bool = typer.Option(
        False,
        "--set-default-profile",
        help="Set the selected OpenAI-compatible profile as default",
    ),
    fastfold_api_key: Optional[str] = typer.Option(
        None, "--fastfold-api-key", help="Fastfold AI Cloud API key (non-interactive mode)"
    ),
    boltz_api_key: Optional[str] = typer.Option(
        None, "--boltz-api-key", help="Boltz API key (non-interactive mode)"
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="LLM provider(s): anthropic, openai, openai_compatible"
    ),
    skills: Optional[str] = typer.Option(
        None, "--skills", help="Comma-separated skill names/sources to install non-interactively"
    ),
    skip_skills: bool = typer.Option(
        False, "--skip-skills", help="Skip the agent-skills install step"
    ),
    datasets: Optional[str] = typer.Option(
        None,
        "--datasets",
        help="Comma-separated datasets to download non-interactively (e.g. 'depmap,msigdb' or 'all')",
    ),
    skip_datasets: bool = typer.Option(
        False, "--skip-datasets", help="Skip the dataset download step"
    ),
):
    """Interactive setup wizard — configure fastfold for first use."""
    from agent.config import Config

    # setup_cmd is also called directly from Python paths (first-run flows),
    # where Typer option defaults remain OptionInfo objects.
    if isinstance(api_key, OptionInfo):
        api_key = None
    if isinstance(openai_api_key, OptionInfo):
        openai_api_key = None
    if isinstance(openai_base_url, OptionInfo):
        openai_base_url = None
    if isinstance(openai_compatible_backend, OptionInfo):
        openai_compatible_backend = None
    if isinstance(profile_label, OptionInfo):
        profile_label = None
    if isinstance(profile_template, OptionInfo):
        profile_template = None
    if isinstance(profile_endpoint, OptionInfo):
        profile_endpoint = None
    if isinstance(profile_key, OptionInfo):
        profile_key = None
    if isinstance(profile_default_model, OptionInfo):
        profile_default_model = None
    if isinstance(set_default_profile, OptionInfo):
        set_default_profile = False
    if isinstance(fastfold_api_key, OptionInfo):
        fastfold_api_key = None
    if isinstance(boltz_api_key, OptionInfo):
        boltz_api_key = None
    if isinstance(provider, OptionInfo):
        provider = None
    if isinstance(skills, OptionInfo):
        skills = None
    if isinstance(skip_skills, OptionInfo):
        skip_skills = False
    if isinstance(datasets, OptionInfo):
        datasets = None
    if isinstance(skip_datasets, OptionInfo):
        skip_datasets = False

    if profile_endpoint and not openai_base_url:
        openai_base_url = profile_endpoint
    if profile_template and not openai_compatible_backend:
        openai_compatible_backend = profile_template
    openai_compatible_backend = _normalize_compatible_backend_name(openai_compatible_backend) or None

    cfg = Config.load()

    default_provider = str(provider or cfg.get("llm.provider", "anthropic") or "anthropic").strip().lower()
    if default_provider not in {"anthropic", "openai", "openai_compatible"}:
        default_provider = "anthropic"

    # Azure AI Foundry: skip interactive key prompt when Foundry is configured
    if (
        default_provider == "anthropic"
        and (os.environ.get("ANTHROPIC_FOUNDRY_API_KEY") or os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE"))
    ):
        console.print("\n  [green]Azure AI Foundry detected. No API key needed.[/green]")
        cfg.set("llm.provider", "anthropic")
        cfg.save()
        return

    console.print()
    console.print(
        Panel(
            "[bold]This wizard will help you configure Fastfold Agent CLI.[/bold]\n"
            "Press Ctrl+C at any time to cancel.",
            title="[cyan]Fastfold Setup Wizard[/cyan]",
            border_style="#00bcd4",
        )
    )
    console.print()

    if provider:
        selected_providers = _parse_provider_list(provider)
    else:
        selected_providers = _prompt_setup_providers(default_provider)

    resolved_openai_base_url: Optional[str] = None
    resolved_openai_backend: Optional[str] = None
    resolved_openai_compatible_model: Optional[str] = None
    selected_compatible_profile_id: Optional[str] = None
    selected_compatible_profile: Optional[dict] = None
    resolved_compatible_profile_label = str(profile_label or "").strip() or None
    if "openai_compatible" in selected_providers:
        selected_compatible_profile_id = _find_compatible_profile_id_by_label(
            cfg, resolved_compatible_profile_label
        )
        if selected_compatible_profile_id is None and not resolved_compatible_profile_label:
            selected_compatible_profile_id = _prompt_setup_compatible_profile_id(cfg)
        if selected_compatible_profile_id:
            selected_compatible_profile = cfg.get_openai_profile(selected_compatible_profile_id)
            if selected_compatible_profile:
                selected_profile_label = str(
                    selected_compatible_profile.get("label") or selected_compatible_profile_id
                ).strip()
                selected_profile_backend = str(
                    selected_compatible_profile.get("backend") or "other"
                ).strip().lower()
                selected_profile_endpoint = str(
                    selected_compatible_profile.get("base_url") or ""
                ).strip()
                backend_name = _compatible_backend_display_name(selected_profile_backend)
                endpoint_text = selected_profile_endpoint or "—"
                console.print(
                    f"  [dim]Using existing compatible profile:[/dim] {selected_profile_label} "
                    f"[dim]({backend_name}, {endpoint_text})[/dim]"
                )
                if not openai_compatible_backend:
                    openai_compatible_backend = str(
                        selected_compatible_profile.get("backend") or ""
                    ).strip().lower() or None
                if not openai_base_url:
                    openai_base_url = str(
                        selected_compatible_profile.get("base_url") or ""
                    ).strip() or None
                if not profile_default_model:
                    profile_default_model = str(
                        selected_compatible_profile.get("default_model") or ""
                    ).strip() or None
                if not resolved_compatible_profile_label:
                    resolved_compatible_profile_label = str(
                        selected_compatible_profile.get("label") or ""
                    ).strip() or None
        resolved_openai_base_url, resolved_openai_backend = _resolve_openai_compatible_endpoint(
            cfg,
            cli_base_url=openai_base_url,
            cli_backend=openai_compatible_backend,
        )
        if not resolved_compatible_profile_label:
            label_defaults = {
                "ollama": "Ollama Local",
                "unsloth": "Unsloth Local",
                "omlx": "oMLX Local",
                "ds4": "DS4 Local",
                "llama_cpp": "llama.cpp Local",
                "lm_studio": "LM Studio Local",
                "other": "Custom Compatible Endpoint",
            }
            resolved_compatible_profile_label = label_defaults.get(
                str(resolved_openai_backend or "").strip().lower(),
                "Compatible Endpoint",
            )
    elif "openai" in selected_providers:
        resolved_openai_base_url = _resolve_openai_base_url(
            cfg,
            cli_base_url=openai_base_url,
            force_mode="cloud",
        )

    resolved_keys: dict[str, str] = {}
    for prov in selected_providers:
        cli_key_for_provider = api_key
        if prov == "openai":
            cli_key_for_provider = openai_api_key
        elif prov in ("xai", "google", "nvidia", "opencode"):
            cli_key_for_provider = None
        elif prov == "openai_compatible":
            cli_key_for_provider = profile_key or openai_api_key
            if not cli_key_for_provider and selected_compatible_profile:
                cli_key_for_provider = str(
                    selected_compatible_profile.get("api_key") or ""
                ).strip() or None
        chosen_key = _resolve_provider_key(
            cfg,
            provider=prov,
            cli_key=cli_key_for_provider,
            openai_base_url=resolved_openai_base_url if prov == "openai_compatible" else None,
            compatible_backend=resolved_openai_backend if prov == "openai_compatible" else None,
        )
        if prov == "anthropic" and (not chosen_key or not chosen_key.startswith("sk-ant-")):
            console.print(
                "\n  [yellow]Warning:[/yellow] Key doesn't start with 'sk-ant-'. "
                "Anthropic API keys typically begin with 'sk-ant-api03-'."
            )
            try:
                proceed = input("  Continue anyway? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("\n  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
            if proceed not in ("y", "yes"):
                console.print("  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
        resolved_keys[prov] = chosen_key
        if (
            prov == "openai_compatible"
            and resolved_openai_base_url
            and resolved_openai_backend
        ):
            backend_name = (
                "oMLX"
                if str(resolved_openai_backend).strip().lower() == "omlx"
                else "Ollama"
                if str(resolved_openai_backend).strip().lower() == "ollama"
                else "Unsloth"
                if str(resolved_openai_backend).strip().lower() == "unsloth"
                else "Custom"
            )
            profile_name = str(resolved_compatible_profile_label or "Compatible Endpoint").strip()
            console.print(
                f"  [dim]Profile:[/dim] {profile_name}  "
                f"[dim]Template:[/dim] {backend_name}  "
                f"[dim]Endpoint:[/dim] {resolved_openai_base_url}"
            )
            compatible_model_choice = _prompt_compatible_model_for_setup(
                cfg,
                base_url=resolved_openai_base_url,
                backend=resolved_openai_backend,
                api_key=chosen_key,
            )
            if isinstance(compatible_model_choice, tuple):
                resolved_openai_compatible_model = compatible_model_choice[0]
                retry_key_override = str(compatible_model_choice[1] or "").strip()
                if retry_key_override:
                    resolved_keys[prov] = retry_key_override
            else:
                resolved_openai_compatible_model = compatible_model_choice
            if not resolved_openai_compatible_model and profile_default_model:
                resolved_openai_compatible_model = str(profile_default_model).strip() or None

    # Determine Fastfold AI Cloud API key (optional, but recommended for cloud-integrated skills)
    cloud_key = _prompt_fastfold_cloud_api_key(cfg, fastfold_api_key)
    boltz_key = _prompt_boltz_api_key(cfg, boltz_api_key)

    # Save
    resolved_compatible_profile_id: Optional[str] = None
    for prov, key in resolved_keys.items():
        if prov == "openai":
            cfg.set("llm.openai_api_key", key)
            cfg.upsert_openai_profile(
                profile_id="openai_cloud",
                label="OpenAI Cloud",
                backend="openai",
                base_url="https://api.openai.com/v1",
                api_key=key,
            )
        elif prov == "openai_compatible":
            backend = str(resolved_openai_backend or "").strip().lower() or "other"
            default_endpoints = {
                "ollama": "http://localhost:11434/v1",
                "unsloth": "http://localhost:8888/v1",
                "omlx": "http://localhost:8000/v1",
            }
            endpoint = (
                _normalize_openai_base_url(resolved_openai_base_url)
                or default_endpoints.get(backend, "http://localhost:11434/v1")
            )
            profile_id = selected_compatible_profile_id or _find_compatible_profile_id_by_label(
                cfg, resolved_compatible_profile_label
            )
            desired_model = (
                str(profile_default_model or "").strip()
                or str(resolved_openai_compatible_model or "").strip()
                or None
            )
            resolved_compatible_profile_id = cfg.upsert_openai_profile(
                profile_id=profile_id,
                label=resolved_compatible_profile_label,
                backend=backend,
                base_url=endpoint,
                api_key=key,
                default_model=desired_model,
                set_active=True,
                set_default=set_default_profile,
            )
            if desired_model:
                cfg.set("llm.model", desired_model)
        elif prov == "anthropic":
            cfg.set("llm.anthropic_api_key", key)
        elif prov in ("xai", "google", "nvidia", "opencode"):
            from agent.config import OPENAI_COMPATIBLE_PROVIDERS

            cfg.set(OPENAI_COMPATIBLE_PROVIDERS[prov]["config_key"], key)
    active_setup_provider = default_provider if default_provider in selected_providers else selected_providers[0]
    cfg.set("llm.provider", _setup_provider_runtime_id(active_setup_provider))
    # Ensure a sensible default model when activating a first-party
    # OpenAI-compatible provider (xAI / Google Gemini / NVIDIA / OpenCode Go).
    from agent.config import OPENAI_COMPATIBLE_PROVIDERS as _OCP

    if active_setup_provider in _OCP:
        meta = _OCP[active_setup_provider]
        current_model = str(cfg.get("llm.model") or "").strip().lower()
        default_model = str(meta.get("default_model") or "")
        prefixes = {
            "xai": "grok",
            "google": "gemini",
            "nvidia": "nvidia/",
            "opencode": "",
        }
        prefix = prefixes.get(active_setup_provider, "")
        if default_model and (not prefix or not current_model.startswith(prefix)):
            cfg.set("llm.model", default_model)
    if active_setup_provider == "openai":
        if "openai_compatible" in selected_providers and resolved_compatible_profile_id:
            cfg.set_openai_active_profile(resolved_compatible_profile_id)
        else:
            cfg.set_openai_active_profile("openai_cloud")
    if set_default_profile and "openai" in selected_providers and "openai_compatible" not in selected_providers:
        cfg.set_openai_default_profile("openai_cloud")
    if cloud_key:
        cfg.set("api.fastfold_cloud_key", cloud_key)
        # Make available immediately to subprocess tools/skills in this run.
        os.environ["FASTFOLD_API_KEY"] = cloud_key
    if boltz_key:
        cfg.set("api.boltz_api_key", boltz_key)
        os.environ["BOLTZ_API_KEY"] = boltz_key
    cfg.save()
    provider_labels = ", ".join(
        (
            "OpenAI"
            if p == "openai"
            else "OpenAI-compatible"
            if p == "openai_compatible"
            else "xAI"
            if p == "xai"
            else "Google Gemini"
            if p == "google"
            else "NVIDIA"
            if p == "nvidia"
            else "OpenCode Zen"
            if p == "opencode"
            else "Anthropic"
        )
        for p in selected_providers
    )
    console.print(
        f"\n  [green]{provider_labels} API key(s) saved to ~/.fastfold-cli/config.json[/green]"
    )
    if cloud_key:
        console.print("  [green]Fastfold AI Cloud API key saved.[/green]")
    else:
        console.print(
            "  [yellow]Fastfold AI Cloud API key skipped.[/yellow] "
            f"Set later with `fastfold config set api.fastfold_cloud_key <key>` "
            f"or visit {FASTFOLD_CLOUD_API_KEYS_URL}"
        )
    if boltz_key:
        console.print("  [green]Boltz API key saved.[/green]")
    else:
        console.print(
            "  [yellow]Boltz API key skipped.[/yellow] "
            "Set later with `fastfold config set api.boltz_api_key <key>` "
            f"or visit {BOLTZ_API_KEYS_URL}"
        )

    # Optional: install agent skills (live catalog + custom sources)
    _prompt_install_skills(skills_arg=skills, skip=skip_skills)
    _prompt_install_boltz_stack(boltz_key)

    # Optional: download local datasets (auto-downloadable ones, all preselected)
    _prompt_install_datasets(datasets_arg=datasets, skip=skip_datasets)

    # Quick health check
    console.print()
    console.print("  [cyan]Running health check...[/cyan]")
    from agent.doctor import run_checks, to_table, has_errors

    checks = run_checks(cfg)
    console.print(to_table(checks))

    if has_errors(checks):
        console.print(
            "\n  [yellow]Some issues detected.[/yellow] Run `fastfold doctor` for details."
        )
    else:
        console.print("\n  [green]All checks passed.[/green]")

    # Done
    console.print()
    console.print(
        Panel(
            "[bold green]You're all set![/bold green]\n\n"
            "  [cyan]fastfold[/cyan]                      Interactive mode\n"
            '  [cyan]fastfold "your question"[/cyan]      Single query\n'
            "  [cyan]fastfold doctor[/cyan]               Full health check\n"
            "  [cyan]fastfold keys[/cyan]                 Optional API keys",
            title="[green]Quick Start[/green]",
            border_style="green",
        )
    )


def _prompt_api_key() -> str:
    """Prompt user for API key with masked input."""
    console.print(
        "  Get your key at: [link=https://console.anthropic.com/settings/keys]https://console.anthropic.com/settings/keys[/link]"
    )
    console.print()
    try:
        key = _prompt_masked_secret("  Enter your Anthropic API key: ")
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key.strip()


def _prompt_provider_api_key(label: str, signup_url: str) -> str:
    """Prompt for a first-party provider API key (xAI / Google Gemini)."""
    console.print(f"  Get your key at: [link={signup_url}]{signup_url}[/link]")
    console.print()
    try:
        key = _prompt_masked_secret(f"  Enter your {label} API key: ")
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key.strip()


def _prompt_openai_api_key() -> str:
    """Prompt user for OpenAI API key with masked input."""
    console.print(
        "  Get your key at: [link=https://platform.openai.com/api-keys]https://platform.openai.com/api-keys[/link]"
    )
    console.print()
    try:
        key = _prompt_masked_secret("  Enter your OpenAI API key: ")
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key.strip()


def _prompt_openai_compatible_api_key(backend: str = "other") -> str:
    """Prompt for OpenAI-compatible API key with backend-aware hints."""
    backend_type = _normalize_compatible_backend_name(backend)
    if backend_type == "unsloth":
        console.print(
            "  Unsloth Studio: [link=http://localhost:8888]http://localhost:8888[/link]"
        )
        console.print("  [dim]Use your Unsloth key (often starts with sk-unsloth-).[/dim]")
    elif backend_type == "ollama":
        console.print(
            "  [dim]Ollama often accepts placeholder keys (for example: ollama).[/dim]"
        )
    elif backend_type == "omlx":
        console.print(
            "  oMLX endpoint: [link=http://localhost:8000]http://localhost:8000[/link]"
        )
        console.print("  [dim]Use your oMLX key if your endpoint requires auth.[/dim]")
    elif backend_type == "ds4":
        console.print(
            "  DS4 endpoint: [link=http://localhost:8000]http://localhost:8000[/link]"
        )
        console.print("  [dim]Use your DS4 token if your server requires auth.[/dim]")
    elif backend_type == "llama_cpp":
        console.print(
            "  llama.cpp endpoint: [link=http://localhost:8080]http://localhost:8080[/link]"
        )
        console.print("  [dim]llama.cpp servers often run without auth, but API keys are supported.[/dim]")
    elif backend_type == "lm_studio":
        console.print(
            "  LM Studio endpoint: [link=http://localhost:1234]http://localhost:1234[/link]"
        )
        console.print("  [dim]LM Studio OpenAI-compatible server usually uses /v1 models discovery.[/dim]")
    else:
        console.print(
            "  [dim]Using a custom OpenAI-compatible endpoint key.[/dim]"
        )
    console.print()
    try:
        key = _prompt_masked_secret("  Enter your OpenAI-compatible API key: ")
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key.strip()


def _prompt_openai_api_key_with_default(default_key: str = "ollama") -> str:
    """Prompt for OpenAI-compatible API key with a default fallback."""
    console.print(
        "  [dim]OpenAI-compatible endpoint detected.[/dim] "
        f"Press Enter to use default key: [green]{default_key}[/green]"
    )
    console.print()
    try:
        key = _prompt_masked_secret(f"  Enter API key [{default_key}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key or default_key


def _is_openai_managed_base_url(base_url: Optional[str]) -> bool:
    """Return True for OpenAI-managed hosts, False for compatible gateways."""
    value = str(base_url or "").strip()
    if not value:
        return True
    try:
        host = (urlparse(value).hostname or "").strip().lower()
    except Exception:
        return False
    if not host:
        return False
    return host == "api.openai.com" or host.endswith(".openai.com")


def _normalize_openai_base_url(base_url: Optional[str]) -> Optional[str]:
    value = str(base_url or "").strip().rstrip("/")
    return value or None


def _normalize_compatible_backend_name(backend: Optional[str]) -> str:
    """Normalize backend aliases to canonical compatible backend ids."""
    value = str(backend or "").strip().lower()
    aliases = {
        "ollama": "ollama",
        "unsloth": "unsloth",
        "omlx": "omlx",
        "ds4": "ds4",
        "deepseek": "ds4",
        "deepseek-v4": "ds4",
        "deepseek_4": "ds4",
        "llama.cpp": "llama_cpp",
        "llama_cpp": "llama_cpp",
        "llama-cpp": "llama_cpp",
        "llamacpp": "llama_cpp",
        "lmstudio": "lm_studio",
        "lm_studio": "lm_studio",
        "lm-studio": "lm_studio",
        "lm studio": "lm_studio",
        "custom": "other",
        "generic": "other",
        "other": "other",
    }
    return aliases.get(value, value)


def _compatible_backend_display_name(backend: Optional[str]) -> str:
    """Return user-facing backend label."""
    backend_type = _normalize_compatible_backend_name(backend)
    if backend_type == "omlx":
        return "oMLX"
    if backend_type == "ollama":
        return "Ollama"
    if backend_type == "unsloth":
        return "Unsloth"
    if backend_type == "ds4":
        return "DS4"
    if backend_type == "llama_cpp":
        return "llama.cpp"
    if backend_type == "lm_studio":
        return "LM Studio"
    return "Custom"


def _compatible_default_endpoint(backend: str, fallback: str = "http://localhost:11434/v1") -> str:
    """Return the default endpoint URL for a compatible backend."""
    defaults = {
        "unsloth": "http://localhost:8888/v1",
        "omlx": "http://localhost:8000/v1",
        "ds4": "http://localhost:8000/v1",
        "llama_cpp": "http://localhost:8080/v1",
        "lm_studio": "http://localhost:1234/v1",
        "ollama": "http://localhost:11434/v1",
    }
    return defaults.get(_normalize_compatible_backend_name(backend), fallback)


def _compatible_install_url(backend: str) -> str:
    """Return install/reference URL for a compatible backend template."""
    backend_type = _normalize_compatible_backend_name(backend)
    urls = {
        "ollama": "https://github.com/ollama/ollama",
        "unsloth": "https://github.com/unslothai/unsloth",
        "omlx": "https://github.com/jundot/omlx",
        "ds4": "https://github.com/antirez/ds4",
        "llama_cpp": "https://github.com/ggml-org/llama.cpp",
        "lm_studio": "https://lmstudio.ai/docs/developer/openai-compat",
        "other": "",
    }
    return urls.get(backend_type, urls["other"])


def _prompt_openai_endpoint_mode(default_mode: str = "cloud") -> str:
    """Prompt whether to use OpenAI cloud or custom compatible endpoint."""
    default_mode = "compatible" if str(default_mode).strip().lower() == "compatible" else "cloud"

    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import questionary
            from prompt_toolkit.styles import Style

            selector_style = Style.from_dict(
                {
                    "qmark": "fg:#00bcd4 bold",
                    "question": "bold",
                    "answer": "fg:#4caf50 bold",
                    "pointer": "fg:#4caf50",
                    "highlighted": "noreverse bold",
                    "selected": "fg:#4caf50 bold",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )
            selected = questionary.select(
                "OpenAI setup mode",
                choices=[
                    questionary.Choice(
                        title="OpenAI cloud (api.openai.com)",
                        value="cloud",
                    ),
                    questionary.Choice(
                        title="OpenAI-compatible custom endpoint (Ollama/Unsloth/vLLM/LM Studio/proxy)",
                        value="compatible",
                    ),
                ],
                default=default_mode,
                instruction="(↑/↓ move, enter confirm)",
                style=selector_style,
                qmark="❯",
            ).ask()
            if selected is None:
                console.print("  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
            return "compatible" if selected == "compatible" else "cloud"
        except typer.Exit:
            raise
        except Exception:
            pass

    console.print("\n  [cyan]OpenAI setup mode[/cyan]")
    console.print("  [dim]Options:[/dim] cloud (c), compatible (k)")
    prompt_default = "compatible" if default_mode == "compatible" else "cloud"
    console.print(f"  [dim]Press Enter to keep default:[/dim] {prompt_default}")
    try:
        raw = input("  Mode: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    if not raw:
        return prompt_default
    if raw in {"compatible", "compat", "custom", "k"}:
        return "compatible"
    if raw in {"cloud", "openai", "c"}:
        return "cloud"
    console.print("  [yellow]Invalid mode selection; defaulting to cloud.[/yellow]")
    return "cloud"


def _resolve_openai_base_url(
    cfg,
    cli_base_url: Optional[str] = None,
    force_mode: Optional[str] = None,
) -> Optional[str]:
    """Resolve OpenAI-compatible base URL from CLI/config/prompt.

    Returns None for OpenAI default endpoint to avoid redundant config writes.
    """
    mode_override = str(force_mode or "").strip().lower()

    if cli_base_url is not None:
        normalized = _normalize_openai_base_url(cli_base_url)
        if not normalized:
            return None
        if mode_override == "compatible":
            return normalized
        if _is_openai_managed_base_url(normalized):
            return None
        return normalized

    existing = _normalize_openai_base_url(cfg.get("llm.openai_base_url"))
    if mode_override in {"cloud", "compatible"}:
        mode = mode_override
    else:
        default_mode = "compatible" if (existing and not _is_openai_managed_base_url(existing)) else "cloud"
        mode = _prompt_openai_endpoint_mode(default_mode=default_mode)
    if mode != "compatible":
        return None
    default_endpoint = existing if (existing and not _is_openai_managed_base_url(existing)) else "http://localhost:11434/v1"
    console.print("\n  [cyan]OpenAI endpoint setup[/cyan]")
    console.print(
        "  [dim]Examples: OpenAI cloud, Ollama, Unsloth, oMLX, DS4, llama.cpp, LM Studio, vLLM, proxy gateways[/dim]"
    )

    try:
        entered = input(f"  Endpoint base URL [{default_endpoint}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    chosen = _normalize_openai_base_url(entered or default_endpoint)
    if not chosen or _is_openai_managed_base_url(chosen):
        return None
    return chosen


def _infer_openai_compatible_backend(base_url: Optional[str], key: Optional[str] = None) -> str:
    """Infer compatible backend type from endpoint/key hints."""
    endpoint = str(base_url or "").strip().lower()
    secret = str(key or "").strip().lower()
    if secret.startswith("sk-unsloth-") or "8888" in endpoint:
        return "unsloth"
    if (
        secret.startswith("dsv4-")
        or secret.startswith("sk-ds4-")
        or "deepseek-v4" in endpoint
        or "deepseek4" in endpoint
        or "ds4" in endpoint
    ):
        return "ds4"
    if "1234" in endpoint or "lmstudio" in endpoint or "lm-studio" in endpoint:
        return "lm_studio"
    if (
        "8080" in endpoint
        or "llama.cpp" in endpoint
        or "llama-cpp" in endpoint
        or "llamacpp" in endpoint
    ):
        return "llama_cpp"
    if secret.startswith("sk-omlx-") or "omlx" in endpoint:
        return "omlx"
    if "11434" in endpoint or "ollama" in endpoint:
        return "ollama"
    if "8000" in endpoint:
        return "omlx"
    return "other"


def _prompt_openai_compatible_backend(default_backend: str = "ollama") -> str:
    """Prompt backend type for OpenAI-compatible setup."""
    normalized_default = _normalize_compatible_backend_name(default_backend)
    if normalized_default not in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}:
        normalized_default = "ollama"

    console.print("\n  [cyan]Endpoint type[/cyan]")
    console.print(f"    [1] Ollama (/api/tags) - {_compatible_install_url('ollama')}")
    console.print(f"    [2] Unsloth (/v1/models, auth) - {_compatible_install_url('unsloth')}")
    console.print(f"    [3] oMLX (/v1/models, auth) - {_compatible_install_url('omlx')}")
    console.print(f"    [4] DS4 (DeepSeek v4, /v1/models) - {_compatible_install_url('ds4')}")
    console.print(f"    [5] llama.cpp (/v1/models) - {_compatible_install_url('llama_cpp')}")
    console.print(f"    [6] LM Studio (/v1/models) - {_compatible_install_url('lm_studio')}")
    console.print("    [7] Other OpenAI-compatible (/v1/models then /api/tags)")
    default_num = {
        "ollama": "1",
        "unsloth": "2",
        "omlx": "3",
        "ds4": "4",
        "llama_cpp": "5",
        "lm_studio": "6",
        "other": "7",
    }[normalized_default]
    try:
        raw = input(f"  Select endpoint type [{default_num}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    if not raw:
        return normalized_default
    if raw in {"1", "ollama", "o"}:
        return "ollama"
    if raw in {"2", "unsloth", "u"}:
        return "unsloth"
    if raw in {"3", "omlx", "m"}:
        return "omlx"
    if raw in {"4", "ds4", "deepseek", "deepseek-v4"}:
        return "ds4"
    if raw in {"5", "llama.cpp", "llama_cpp", "llama-cpp", "llamacpp"}:
        return "llama_cpp"
    if raw in {"6", "lmstudio", "lm_studio", "lm-studio", "lm studio"}:
        return "lm_studio"
    if raw in {"7", "other", "custom", "k"}:
        return "other"
    console.print("  [dim]Invalid selection; using generic compatible mode.[/dim]")
    return "other"


def _resolve_openai_compatible_endpoint(
    cfg,
    cli_base_url: Optional[str] = None,
    cli_backend: Optional[str] = None,
) -> tuple[str, str]:
    """Resolve compatible endpoint URL and backend type for setup."""
    existing = _normalize_openai_base_url(cfg.get("llm.openai_base_url"))
    existing_key = cfg.get("llm.openai_compatible_api_key")
    configured_backend = _normalize_compatible_backend_name(
        str(cfg.get("llm.openai_compatible_backend") or "").strip().lower()
    )
    inferred_backend = _infer_openai_compatible_backend(existing, existing_key)
    default_backend = (
        configured_backend
        if configured_backend in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}
        else inferred_backend
    )
    selected_backend = _normalize_compatible_backend_name(cli_backend)
    if selected_backend not in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}:
        selected_backend = _prompt_openai_compatible_backend(default_backend=default_backend)

    if cli_base_url is not None:
        chosen = _normalize_openai_base_url(cli_base_url)
        if not chosen:
            chosen = _compatible_default_endpoint(selected_backend)
        if _is_openai_managed_base_url(chosen):
            console.print("  [yellow]OpenAI cloud URL detected; using compatible default endpoint instead.[/yellow]")
            chosen = _compatible_default_endpoint(selected_backend)
        return chosen, selected_backend

    if selected_backend != "other":
        default_endpoint = _compatible_default_endpoint(selected_backend)
    else:
        default_endpoint = existing if (existing and not _is_openai_managed_base_url(existing)) else "http://localhost:11434/v1"

    console.print("\n  [cyan]OpenAI endpoint setup[/cyan]")
    console.print(
        "  [dim]Examples: Ollama, Unsloth, oMLX, DS4, llama.cpp, LM Studio, vLLM, proxy gateways[/dim]"
    )
    try:
        entered = input(f"  Endpoint base URL [{default_endpoint}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    chosen = _normalize_openai_base_url(entered or default_endpoint)
    if not chosen or _is_openai_managed_base_url(chosen):
        chosen = default_endpoint
    return chosen, selected_backend


def _find_compatible_profile_id_by_label(cfg, label: Optional[str]) -> Optional[str]:
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


def _prompt_setup_compatible_profile_id(cfg) -> Optional[str]:
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


def _ollama_tags_url_from_base(base_url: str) -> str:
    """Build an Ollama /api/tags URL from an OpenAI-compatible base URL."""
    parsed = urlparse(str(base_url or "").strip())
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    tags_path = f"{path}/api/tags" if path else "/api/tags"
    return parsed._replace(path=tags_path, query="", fragment="").geturl()


def _openai_models_url_from_base(base_url: str) -> str:
    """Build a /v1/models URL from an OpenAI-compatible base URL."""
    parsed = urlparse(str(base_url or "").strip())
    path = (parsed.path or "").rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    models_path = f"{path}/models"
    return parsed._replace(path=models_path, query="", fragment="").geturl()


def _truncate_discovery_detail(text: str, max_chars: int = 320) -> str:
    value = str(text or "").strip()
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + f"... [{len(value)} chars total]"


def _extract_discovery_error_message(raw: str) -> str:
    """Extract concise API error messages from JSON payloads when available."""
    value = str(raw or "").strip()
    if not value:
        return ""
    try:
        payload = json.loads(value)
    except Exception:
        return value

    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            msg = str(err.get("message") or err.get("detail") or "").strip()
            code = str(err.get("code") or "").strip()
            if msg:
                return f"{msg} (code={code})" if code else msg
        for key in ("message", "detail", "description", "error_description"):
            msg = payload.get(key)
            if isinstance(msg, str) and msg.strip():
                return msg.strip()
    return value


def _read_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        body = exc.read()
    except Exception:
        return ""
    if not body:
        return ""
    return body.decode("utf-8", errors="replace").strip()


def _report_discovery_http_error(endpoint: str, url: str, exc: urllib.error.HTTPError) -> None:
    status = int(getattr(exc, "code", 0) or 0)
    reason = str(getattr(exc, "reason", "") or getattr(exc, "msg", "")).strip()
    body_raw = _read_http_error_body(exc)
    body_msg = _extract_discovery_error_message(body_raw)

    console.print(
        f"  [yellow]{endpoint} request failed[/yellow] "
        f"[dim](status={status or 'unknown'}, url={url})[/dim]"
    )
    if reason:
        console.print(f"  [dim]Reason:[/dim] {reason}")
    if body_msg:
        console.print(
            f"  [dim]Response:[/dim] {_truncate_discovery_detail(body_msg)}",
            markup=False,
        )


def _report_discovery_exception(endpoint: str, url: str, exc: Exception) -> None:
    console.print(f"  [yellow]{endpoint} request failed[/yellow] [dim](url={url})[/dim]")
    console.print(
        f"  [dim]Error:[/dim] {_truncate_discovery_detail(str(exc))}",
        markup=False,
    )


def _fetch_openai_models_for_setup(base_url: str, api_key: Optional[str] = None) -> list[str]:
    """Fetch model IDs from OpenAI-compatible /v1/models."""
    url = _openai_models_url_from_base(base_url)
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with spinner("Discovering models from /v1/models..."):
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        _report_discovery_http_error("/v1/models", url, exc)
        return []
    except (urllib.error.URLError, TimeoutError) as exc:
        _report_discovery_exception("/v1/models", url, exc)
        return []
    except Exception as exc:
        _report_discovery_exception("/v1/models", url, exc)
        return []
    try:
        payload = json.loads(text) if text else {}
    except Exception:
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    names = sorted({str(item.get("id") or "").strip() for item in data if isinstance(item, dict)} - {""})
    if names:
        console.print(f"  [green]Found {len(names)} model(s) from /v1/models.[/green]")
    return names


def _fetch_ollama_tags_for_setup(base_url: str, api_key: Optional[str] = None) -> list[str]:
    """Fetch model names from Ollama /api/tags."""
    url = _ollama_tags_url_from_base(base_url)
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with spinner("Discovering models from /api/tags..."):
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        _report_discovery_http_error("/api/tags", url, exc)
        return []
    except (urllib.error.URLError, TimeoutError) as exc:
        _report_discovery_exception("/api/tags", url, exc)
        return []
    except Exception as exc:
        _report_discovery_exception("/api/tags", url, exc)
        return []
    try:
        payload = json.loads(text) if text else {}
    except Exception:
        return []
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    names = sorted({str(item.get("name") or "").strip() for item in models if isinstance(item, dict)} - {""})
    if names:
        console.print(f"  [green]Found {len(names)} model(s) from /api/tags.[/green]")
    return names


def _fetch_compatible_models_for_setup(base_url: str, backend: str, api_key: Optional[str] = None) -> list[str]:
    """Discover compatible models based on selected backend."""
    backend_type = _normalize_compatible_backend_name(backend)
    if backend_type in {"unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
        names = _fetch_openai_models_for_setup(base_url, api_key=api_key)
    elif backend_type == "ollama":
        names = _fetch_ollama_tags_for_setup(base_url, api_key=api_key)
        if not names:
            names = _fetch_openai_models_for_setup(base_url, api_key=api_key)
    else:
        names = _fetch_openai_models_for_setup(base_url, api_key=api_key)
        if not names:
            names = _fetch_ollama_tags_for_setup(base_url, api_key=api_key)
    if names:
        return names
    console.print(
        "  [yellow]No models found from discovery endpoint(s).[/yellow] "
        "[dim]You can still enter a model manually.[/dim]"
    )
    return []


def _prompt_compatible_model_for_setup(
    cfg,
    base_url: str,
    backend: str,
    api_key: Optional[str] = None,
) -> str | tuple[str, Optional[str]]:
    """Prompt for compatible model selection in setup flow."""
    default_model = str(cfg.get("llm.model") or "").strip() or "llama3.1"
    retry_key_override: Optional[str] = None
    effective_key = str(api_key or "").strip() or None
    discovered = _fetch_compatible_models_for_setup(base_url, backend=backend, api_key=effective_key)

    def _result_with_key(model_id: str) -> str | tuple[str, Optional[str]]:
        if retry_key_override:
            return model_id, retry_key_override
        return model_id

    while not discovered:
        console.print("  [cyan]Model discovery options[/cyan]")
        console.print("    [1] Retry discovery with a new API key")
        console.print("    [2] Enter model ID manually")
        console.print("    [3] Cancel setup")
        try:
            raw_action = input("  Select option [2]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if raw_action in {"3", "cancel", "c", "q"}:
            console.print("  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if raw_action in {"", "2", "manual", "m"}:
            break
        if raw_action not in {"1", "retry", "r"}:
            console.print("  [dim]Invalid selection; switching to manual entry.[/dim]")
            break
        retry_key = _prompt_openai_compatible_api_key(backend=backend)
        if not retry_key:
            console.print("  [dim]Retry skipped; keeping current key.[/dim]")
            continue
        retry_key_override = retry_key
        effective_key = retry_key
        discovered = _fetch_compatible_models_for_setup(base_url, backend=backend, api_key=effective_key)

    if discovered:
        console.print("  [cyan]Available models[/cyan]")
        for idx, name in enumerate(discovered, 1):
            console.print(f"    [{idx}] {name}")
        manual_idx = len(discovered) + 1
        console.print(f"    [{manual_idx}] Enter custom model name")
        try:
            raw_choice = input("  Select model (number): ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if raw_choice.isdigit():
            selected = int(raw_choice)
            if 1 <= selected <= len(discovered):
                return _result_with_key(discovered[selected - 1])
            if selected != manual_idx:
                console.print("  [dim]Invalid selection; switching to manual entry.[/dim]")
        elif raw_choice:
            console.print("  [dim]Invalid selection; switching to manual entry.[/dim]")

    try:
        model_input = input(f"  Model ID [{default_model}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    selected_model = model_input or default_model
    return _result_with_key(selected_model)


def _prompt_masked_secret(message: str) -> str:
    """Prompt for secrets with visible masked characters while typing."""
    # Prefer questionary in interactive terminals (shows mask while typing).
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import questionary
            from prompt_toolkit.styles import Style

            secret_style = Style.from_dict(
                {
                    "qmark": "fg:#00bcd4 bold",
                    "question": "bold",
                    "answer": "fg:#4caf50 bold",
                    "pointer": "fg:#4caf50",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )
            value = questionary.password(
                message.strip(),
                instruction="(input is masked)",
                qmark="❯",
                style=secret_style,
            ).ask()
            if value is None:
                raise KeyboardInterrupt
            return str(value)
        except (EOFError, KeyboardInterrupt):
            raise
        except Exception:
            pass

    # Fallback for non-interactive terminals.
    import getpass

    return getpass.getpass(message)


def _parse_provider_list(raw: str) -> list[str]:
    """Parse provider list from CLI option, preserving canonical order."""
    alias_map = {
        "anthropic": "anthropic",
        "openai": "openai",
        "xai": "xai",
        "grok": "xai",
        "google": "google",
        "gemini": "google",
        "nvidia": "nvidia",
        "nemotron": "nvidia",
        "opencode": "opencode",
        "opencode-go": "opencode",
        "opencode_go": "opencode",
        "go": "opencode",
        "openai_compatible": "openai_compatible",
        "openai-compatible": "openai_compatible",
        "compatible": "openai_compatible",
    }
    requested = set()
    for part in str(raw or "").split(","):
        token = part.strip().lower()
        if not token:
            continue
        requested.add(alias_map.get(token, token))
    selected = [p for p in SETUP_PROVIDER_ORDER if p in requested]
    if not selected:
        valid = ", ".join(SETUP_PROVIDER_ORDER)
        console.print(f"[red]Invalid --provider value '{raw}'. Valid providers: {valid}[/red]")
        raise typer.Exit(code=2)
    return selected


def _prompt_setup_providers(default_provider: str) -> list[str]:
    """Interactive provider selector (arrow keys + space toggles)."""
    options = list(SETUP_PROVIDER_ORDER)
    labels = {
        "anthropic": "Anthropic",
        "openai": "OpenAI",
        "xai": "xAI (Grok)",
        "google": "Google Gemini",
        "nvidia": "NVIDIA",
        "opencode": "OpenCode Zen",
        "openai_compatible": "OpenAI-compatible custom endpoint",
    }
    _ = default_provider

    # Preferred UX in real terminals: questionary inline checklist.
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import questionary
            from prompt_toolkit.styles import Style

            selector_style = Style.from_dict(
                {
                    "qmark": "fg:#00bcd4 bold",
                    "question": "bold",
                    "answer": "fg:#4caf50 bold",
                    "pointer": "fg:#4caf50",
                    "highlighted": "noreverse bold",
                    "selected": "fg:#4caf50 bold",
                    "separator": "fg:#6c6c6c",
                    "disabled": "fg:#858585",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )

            choices = [
                questionary.Choice(
                    title=f"{labels.get(prov, prov.title())}",
                    value=prov,
                    checked=False,
                )
                for prov in options
            ]
            selected = questionary.checkbox(
                "Select provider(s) to configure",
                choices=choices,
                instruction="(↑/↓ move, space toggle, enter confirm)",
                validate=lambda answer: True if answer else "Select at least one provider.",
                style=selector_style,
                qmark="❯",
                pointer="▸",
            ).ask()
            if selected is None:
                console.print("  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
            normalized = {str(v).strip().lower() for v in selected}
            return [p for p in options if p in normalized]
        except typer.Exit:
            raise
        except Exception:
            # Fall back to text input when terminal capabilities are limited.
            pass

    # Plain-text fallback for `fastfold setup` when the interactive checklist
    # (questionary) cannot run — e.g. piped stdin, CI, or limited terminals.
    # Users type provider names or short codes: "anthropic,xai" or "a,x".
    alias_map = {
        "a": "anthropic",
        "anthropic": "anthropic",
        "o": "openai",
        "openai": "openai",
        "x": "xai",
        "xai": "xai",
        "grok": "xai",
        "g": "google",
        "google": "google",
        "gemini": "google",
        "n": "nvidia",
        "nvidia": "nvidia",
        "nemotron": "nvidia",
        "oc": "opencode",
        "opencode": "opencode",
        "opencode-go": "opencode",
        "go": "opencode",
        "k": "openai_compatible",
        "compatible": "openai_compatible",
        "openai-compatible": "openai_compatible",
        "openai_compatible": "openai_compatible",
        "all": "all",
        "both": "all",
    }

    while True:
        console.print("  [cyan]Select provider(s) to configure[/cyan]")
        console.print(
            "  [dim]Options:[/dim] anthropic (a), openai (o), xai (x), google (g), "
            "nvidia (n), opencode (oc), openai_compatible (k), all"
        )
        try:
            raw = input("  Providers: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()

        if not raw:
            console.print("  [yellow]Select at least one provider.[/yellow]")
            continue

        tokens = [t for t in raw.replace(",", " ").split() if t]
        selected: set[str] = set()
        bad: list[str] = []
        for token in tokens:
            mapped = alias_map.get(token)
            if mapped == "all":
                selected.update(options)
            elif mapped in options:
                selected.add(mapped)
            else:
                bad.append(token)

        if bad:
            console.print(f"  [yellow]Invalid selection:[/yellow] {' '.join(bad)}")
            continue
        if not selected:
            console.print("  [yellow]Select at least one provider.[/yellow]")
            continue
        return [p for p in options if p in selected]


def _setup_provider_runtime_id(provider_id: str) -> str:
    """Map setup provider id to runtime llm.provider."""
    return "openai" if provider_id == "openai_compatible" else provider_id


def _resolve_provider_key(
    cfg,
    provider: str,
    cli_key: Optional[str] = None,
    openai_base_url: Optional[str] = None,
    compatible_backend: Optional[str] = None,
) -> str:
    """Resolve provider key from cli arg, existing config, env var, or prompt."""
    provider = str(provider).strip().lower()
    if provider in {"openai", "openai_compatible"}:
        is_compat = provider == "openai_compatible" or (
            bool(openai_base_url) and not _is_openai_managed_base_url(openai_base_url)
        )
        key_config_key = "llm.openai_compatible_api_key" if is_compat else "llm.openai_api_key"
        existing_key = cfg.get(key_config_key) or cfg.llm_api_key("openai")
        env_var_name = "OPENAI_COMPATIBLE_API_KEY" if is_compat else "OPENAI_API_KEY"
        prompt_fn = _prompt_openai_api_key
        label = "OpenAI-compatible" if is_compat else "OpenAI"
        config_key = key_config_key
        backend = _normalize_compatible_backend_name(compatible_backend)
        if backend not in {"ollama", "unsloth", "omlx", "ds4", "llama_cpp", "lm_studio", "other"}:
            backend = _infer_openai_compatible_backend(openai_base_url, existing_key)
        default_compat_key = "ollama" if (is_compat and backend == "ollama") else None
        if is_compat and not default_compat_key:
            prompt_fn = lambda: _prompt_openai_compatible_api_key(backend=backend)
    elif provider in ("xai", "google", "nvidia", "opencode"):
        from agent.config import OPENAI_COMPATIBLE_PROVIDERS

        meta = OPENAI_COMPATIBLE_PROVIDERS[provider]
        existing_key = cfg.llm_api_key(provider)
        env_var_name = meta["env_var"]
        label = meta["label"]
        config_key = meta["config_key"]
        signup_url = meta["signup_url"]
        prompt_fn = lambda: _prompt_provider_api_key(label, signup_url)
        default_compat_key = None
    else:
        existing_key = cfg.llm_api_key("anthropic")
        env_var_name = "ANTHROPIC_API_KEY"
        prompt_fn = _prompt_api_key
        label = "Anthropic"
        config_key = "llm.anthropic_api_key"
        default_compat_key = None

    console.print(f"\n  [cyan]{label} setup[/cyan]")
    if cli_key:
        candidate = cli_key.strip()
        issue = cfg.validate_llm_api_key(
            config_key,
            candidate,
            openai_base_url=openai_base_url,
        )
        if issue:
            console.print(f"  [red]{issue}[/red]")
            raise typer.Exit(code=2)
        return candidate
    if existing_key:
        existing_issue = cfg.validate_llm_api_key(
            config_key,
            existing_key,
            openai_base_url=openai_base_url,
        )
        if existing_issue:
            console.print(
                f"  [yellow]Existing {label} key is invalid and will be replaced:[/yellow] {existing_issue}"
            )
        else:
            masked = existing_key[:7] + "..." + existing_key[-4:] if len(existing_key) > 11 else "***"
            console.print(f"  API key already configured: [green]{masked}[/green]")
            try:
                keep = input("  Keep existing key? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("\n  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
            if keep in ("", "y", "yes"):
                console.print("  [green]Keeping existing key.[/green]")
                return existing_key

    env_key = os.environ.get(env_var_name)
    if env_key:
        env_issue = cfg.validate_llm_api_key(
            config_key,
            env_key,
            openai_base_url=openai_base_url,
        )
        if env_issue:
            console.print(
                f"  [yellow]Ignoring invalid {env_var_name} value:[/yellow] {env_issue}"
            )
        else:
            masked = env_key[:7] + "..." + env_key[-4:] if len(env_key) > 11 else "***"
            console.print(f"  Found {env_var_name} in environment: [green]{masked}[/green]")
            try:
                save_it = input("  Save to fastfold config? [Y/n] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                console.print("\n  [dim]Setup cancelled.[/dim]")
                raise typer.Exit()
            if save_it in ("", "y", "yes"):
                return env_key

    while True:
        if default_compat_key:
            candidate = _prompt_openai_api_key_with_default(default_compat_key)
        else:
            candidate = prompt_fn()
        issue = cfg.validate_llm_api_key(
            config_key,
            candidate,
            openai_base_url=openai_base_url,
        )
        if not issue:
            return candidate
        console.print(f"  [yellow]{issue}[/yellow]")


def _prompt_fastfold_cloud_api_key(cfg, cli_value: Optional[str] = None) -> Optional[str]:
    """Prompt for Fastfold AI Cloud API key, allowing users to keep/skip."""
    existing = cfg.get("api.fastfold_cloud_key") or os.environ.get("FASTFOLD_API_KEY")
    if isinstance(cli_value, str) and cli_value:
        return cli_value.strip() or None

    console.print()
    console.print(
        "  Fastfold AI Cloud API keys: "
        f"[link={FASTFOLD_CLOUD_API_KEYS_URL}]{FASTFOLD_CLOUD_API_KEYS_URL}[/link]"
    )
    if existing:
        masked = existing[:7] + "..." + existing[-4:] if len(existing) > 11 else "***"
        console.print(f"  Existing Fastfold key detected: [green]{masked}[/green]")
        try:
            keep = input("  Keep existing Fastfold key? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if keep in ("", "y", "yes"):
            return existing

    console.print("  Press Enter to skip this step.")
    try:
        key = _prompt_masked_secret("  Enter your Fastfold AI Cloud API key: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key or None


def _prompt_boltz_api_key(cfg, cli_value: Optional[str] = None) -> Optional[str]:
    """Prompt for Boltz API key, allowing users to keep/skip."""
    existing = cfg.get("api.boltz_api_key") or os.environ.get("BOLTZ_API_KEY")
    if isinstance(cli_value, str) and cli_value:
        return cli_value.strip() or None

    console.print()
    console.print(
        "  Boltz API keys: "
        f"[link={BOLTZ_API_KEYS_URL}]{BOLTZ_API_KEYS_URL}[/link]"
    )
    if existing:
        masked = existing[:7] + "..." + existing[-4:] if len(existing) > 11 else "***"
        console.print(f"  Existing Boltz key detected: [green]{masked}[/green]")
        try:
            keep = input("  Keep existing Boltz key? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if keep in ("", "y", "yes"):
            return existing

    console.print("  Press Enter to skip this step.")
    try:
        key = _prompt_masked_secret("  Enter your Boltz API key: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    return key or None


def _find_boltz_cli_path() -> Optional[Path]:
    """Return the first available boltz-api executable path."""
    candidates: list[str] = []
    in_path = shutil.which("boltz-api")
    if in_path:
        candidates.append(in_path)
    candidates.extend(
        [
            str(Path.home() / ".local" / "bin" / "boltz-api"),
            str(Path.home() / ".boltz" / "bin" / "boltz-api"),
        ]
    )
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists() and path.is_file() and os.access(str(path), os.X_OK):
            return path
    return None


def _boltz_cli_version(path: Path) -> str:
    """Return a compact boltz-api version string when available."""
    try:
        proc = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:  # noqa: BLE001
        return "unknown version"
    output = (proc.stdout or proc.stderr or "").strip()
    if not output:
        return "unknown version"
    return output.splitlines()[0].strip()


def _install_boltz_skill_from_setup() -> bool:
    """Install Fastfold's boltz skill if not already present."""
    from agent.skills import install_skill, installed_skill_names

    installed = set(installed_skill_names())
    if "boltz" in installed:
        console.print("  [green]Boltz skill already installed.[/green]")
        return True

    with spinner("Installing Fastfold Boltz skill..."):
        result = install_skill(BOLTZ_SKILL_SOURCE, prefer_npx=True)
    if result.get("ok"):
        console.print(f"  [green]{result.get('summary', 'Installed boltz skill.')}[/green]")
        return True

    console.print(
        "  [yellow]Could not auto-install Boltz skill.[/yellow] "
        f"[dim]{result.get('summary', '')}[/dim]"
    )
    console.print(f"  [dim]Install manually with:[/dim] fastfold skills add {BOLTZ_SKILL_SOURCE}")
    return False


def _ensure_boltz_cli_installed_from_setup() -> bool:
    """Install boltz-api CLI when missing."""
    current = _find_boltz_cli_path()
    if current:
        version = _boltz_cli_version(current)
        console.print(f"  [green]boltz-api ready:[/green] {current} [dim]({version})[/dim]")
        return True

    if not shutil.which("curl") or not shutil.which("sh"):
        console.print(
            "  [yellow]Could not install boltz-api automatically (missing curl/sh).[/yellow]"
        )
        console.print(
            "  [dim]Install manually:[/dim] curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
        )
        return False

    with spinner("Installing boltz-api CLI..."):
        proc = subprocess.run(
            ["sh", "-lc", BOLTZ_INSTALL_SCRIPT],
            capture_output=True,
            text=True,
            timeout=180,
        )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        detail = detail.splitlines()[-1] if detail else "installer exited with a non-zero code"
        console.print(f"  [yellow]boltz-api install failed:[/yellow] {detail}")
        console.print(
            "  [dim]Retry manually:[/dim] curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"
        )
        return False

    installed = _find_boltz_cli_path()
    if not installed:
        console.print(
            "  [yellow]boltz-api installer completed, but executable was not found on disk.[/yellow]"
        )
        return False
    version = _boltz_cli_version(installed)
    console.print(f"  [green]Installed boltz-api:[/green] {installed} [dim]({version})[/dim]")
    return True


def _prompt_install_boltz_stack(boltz_key: Optional[str]) -> None:
    """Offer Boltz skill + CLI installation when a Boltz key is configured."""
    if not boltz_key:
        return

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        console.print(
            "  [dim]Boltz key configured. Optional setup:[/dim] "
            f"`fastfold skills add {BOLTZ_SKILL_SOURCE}` and "
            "`curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh`."
        )
        return

    try:
        answer = input("\n  Install Boltz skill + boltz-api CLI now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Skipped Boltz install step.[/dim]")
        return
    if answer in {"n", "no"}:
        console.print("  [dim]Skipped Boltz install step.[/dim]")
        return

    _install_boltz_skill_from_setup()
    _ensure_boltz_cli_installed_from_setup()


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
    fastfold-owned ~/.fastfold-cli/.claude/skills).
    """
    from collections import OrderedDict
    from agent.skills import install_skill, npx_add, _npx_target, _npx_available

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
    groups: "OrderedDict[str, dict]" = OrderedDict()
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


def _select_skills_from_catalog(catalog: list[dict]) -> list[str]:
    """Let the user pick skills to install from the live catalog. Returns install sources."""
    # Interactive multi-select (questionary) when available.
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import questionary
            from prompt_toolkit.styles import Style

            selector_style = Style.from_dict(
                {
                    "qmark": "fg:#00bcd4 bold",
                    "question": "bold",
                    "answer": "fg:#4caf50 bold",
                    "pointer": "fg:#4caf50",
                    "highlighted": "noreverse bold",
                    "selected": "fg:#4caf50 bold",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )
            choices = [
                questionary.Choice(
                    title=f"{c['name']} — {(c.get('description') or '').strip()[:80]}",
                    value=c["install_source"],
                    checked=True,
                )
                for c in catalog
            ]
            picked = questionary.checkbox(
                "Select skills to install (all selected by default)",
                choices=choices,
                instruction="(↑/↓ move, space toggle, enter confirm — all preselected)",
                style=selector_style,
                qmark="❯",
                pointer="▸",
            ).ask()
            return list(picked or [])
        except typer.Exit:
            raise
        except Exception:
            pass

    # Inline fallback: numbered list + comma-separated selection.
    console.print("  [cyan]Available skills[/cyan] [dim](all installed by default)[/dim]")
    for idx, c in enumerate(catalog, 1):
        console.print(f"    [{idx}] {c['name']} — [dim]{(c.get('description') or '').strip()[:80]}[/dim]")
    try:
        raw = input("  Select skills (comma-separated numbers, 'all', or 'none'; Enter for all): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return []
    if not raw or raw == "all":
        return [c["install_source"] for c in catalog]
    if raw == "none":
        return []
    sources: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit() and 1 <= int(token) <= len(catalog):
            sources.append(catalog[int(token) - 1]["install_source"])
    return sources


def _select_suggested_sources() -> list[str]:
    """Offer curated third-party skill collections (grouped by provider). Returns install sources."""
    from agent.skills import SUGGESTED_SKILL_SOURCES

    if not SUGGESTED_SKILL_SOURCES:
        return []

    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import questionary
            from prompt_toolkit.styles import Style

            selector_style = Style.from_dict(
                {
                    "qmark": "fg:#00bcd4 bold",
                    "question": "bold",
                    "answer": "fg:#4caf50 bold",
                    "pointer": "fg:#4caf50",
                    "highlighted": "noreverse bold",
                    "selected": "fg:#4caf50 bold",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )
            choices = [
                questionary.Choice(
                    title=f"{s['provider']} — {s['description']} ({s['source']})",
                    value=s["source"],
                )
                for s in SUGGESTED_SKILL_SOURCES
            ]
            picked = questionary.checkbox(
                "Suggested community skill collections (optional)",
                choices=choices,
                instruction="(↑/↓ move, space toggle, enter confirm; installs the whole collection)",
                style=selector_style,
                qmark="❯",
                pointer="▸",
            ).ask()
            return list(picked or [])
        except typer.Exit:
            raise
        except Exception:
            pass

    console.print("  [cyan]Suggested community skill collections[/cyan] [dim](installs the whole collection)[/dim]")
    for idx, s in enumerate(SUGGESTED_SKILL_SOURCES, 1):
        console.print(f"    [{idx}] {s['provider']} — [dim]{s['description']} ({s['source']})[/dim]")
    try:
        raw = input("  Select collections (comma-separated numbers, or 'all'; Enter to skip): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return []
    if not raw:
        return []
    if raw == "all":
        return [s["source"] for s in SUGGESTED_SKILL_SOURCES]
    sources: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit() and 1 <= int(token) <= len(SUGGESTED_SKILL_SOURCES):
            sources.append(SUGGESTED_SKILL_SOURCES[int(token) - 1]["source"])
    return sources


def _prompt_install_skills(skills_arg: Optional[str] = None, skip: bool = False) -> None:
    """Setup step: install agent skills from the live Fastfold catalog or custom sources."""
    from agent.skills import discover_skills

    if skip:
        return

    # Non-interactive explicit list (CI/scripting): `--skills a,b,owner/repo@path`
    if skills_arg:
        sources = [s.strip() for s in skills_arg.split(",") if s.strip()]
        if sources:
            console.print("\n  [cyan]Agent skills[/cyan]")
            _install_skill_sources(sources)
        return

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        console.print(
            "\n  [dim]Skipping skills install (non-interactive). "
            "Add later with `fastfold skills find` / `fastfold skills add <source>`.[/dim]"
        )
        return

    console.print("\n  [cyan]Agent skills[/cyan]")
    console.print(
        "  [dim]Skills add guided workflows (folding, MD, protein design, reporting). "
        "They are optional and installed on demand.[/dim]"
    )
    try:
        proceed = input("  Install agent skills now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    if proceed in ("n", "no"):
        console.print(
            "  [dim]Skipped. Add later with `fastfold skills find` / `fastfold skills add <source>`.[/dim]"
        )
        return

    with spinner("Fetching the current Fastfold skills catalog..."):
        catalog = discover_skills()
    selected: list[str] = []
    if catalog:
        selected = _select_skills_from_catalog(catalog)
    else:
        console.print(
            "  [yellow]Could not fetch the catalog[/yellow] [dim](needs git + network). "
            "You can still add suggested or custom sources below.[/dim]"
        )

    # Offer curated third-party collections (K-Dense-AI, Anthropic, DeepMind).
    selected += _select_suggested_sources()

    # Always offer custom sources (GitHub URL / owner/repo@subpath / local path).
    try:
        custom = input(
            "  Add custom skill source(s)? (GitHub URL or owner/repo@path, comma-separated; Enter to skip): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        custom = ""
    if custom:
        selected += [s.strip() for s in custom.split(",") if s.strip()]

    if not selected:
        console.print("  [dim]No skills selected.[/dim]")
        return

    _install_skill_sources(selected)


def _select_datasets_from_catalog(catalog: list[tuple[str, dict]]) -> list[str]:
    """Let the user pick auto-downloadable datasets to download. Returns dataset names."""
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import questionary
            from prompt_toolkit.styles import Style

            selector_style = Style.from_dict(
                {
                    "qmark": "fg:#00bcd4 bold",
                    "question": "bold",
                    "answer": "fg:#4caf50 bold",
                    "pointer": "fg:#4caf50",
                    "highlighted": "noreverse bold",
                    "selected": "fg:#4caf50 bold",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )
            choices = [
                questionary.Choice(
                    title=f"{name} — {(ds.get('description') or '').strip()[:70]} "
                    f"({ds.get('size_hint', '?')})",
                    value=name,
                    checked=True,
                )
                for name, ds in catalog
            ]
            picked = questionary.checkbox(
                "Select datasets to download (all selected by default)",
                choices=choices,
                instruction="(↑/↓ move, space toggle, enter confirm — all preselected)",
                style=selector_style,
                qmark="❯",
                pointer="▸",
            ).ask()
            return list(picked or [])
        except typer.Exit:
            raise
        except Exception:
            pass

    # Inline fallback: numbered list + comma-separated selection.
    console.print("  [cyan]Available datasets[/cyan] [dim](all downloaded by default)[/dim]")
    for idx, (name, ds) in enumerate(catalog, 1):
        console.print(
            f"    [{idx}] {name} — [dim]{(ds.get('description') or '').strip()[:70]} "
            f"({ds.get('size_hint', '?')})[/dim]"
        )
    try:
        raw = input(
            "  Select datasets (comma-separated numbers, 'all', or 'none'; Enter for all): "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return []
    if not raw or raw == "all":
        return [name for name, _ in catalog]
    if raw == "none":
        return []
    names: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit() and 1 <= int(token) <= len(catalog):
            names.append(catalog[int(token) - 1][0])
    return names


def _prompt_install_datasets(datasets_arg: Optional[str] = None, skip: bool = False) -> None:
    """Setup step: download local datasets (auto-downloadable, all preselected)."""
    from data.downloader import DATASETS, download_all, download_dataset

    if skip:
        return

    auto = [(name, ds) for name, ds in DATASETS.items() if ds.get("auto_download")]

    # Non-interactive explicit list (CI/scripting): `--datasets depmap,msigdb` or `all`.
    if datasets_arg:
        arg = datasets_arg.strip().lower()
        console.print("\n  [cyan]Datasets[/cyan]")
        if arg == "all":
            download_all()
            return
        for name in [s.strip() for s in datasets_arg.split(",") if s.strip()]:
            download_dataset(name)
        return

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        console.print(
            "\n  [dim]Skipping dataset download (non-interactive). "
            "Add later with `fastfold data pull-all` or `fastfold data pull <name>`.[/dim]"
        )
        return

    console.print("\n  [cyan]Datasets[/cyan]")
    console.print(
        "  [dim]Optional reference datasets power offline tools (DepMap dependencies, "
        "gene sets, interaction networks). Some are large (depmap is ~580MB).[/dim]"
    )
    try:
        proceed = input("  Download datasets now? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    if proceed not in ("y", "yes"):
        console.print(
            "  [dim]Skipped. Download later with `fastfold data pull-all` "
            "or `fastfold data pull <name>`.[/dim]"
        )
        return

    selected = _select_datasets_from_catalog(auto)
    if not selected:
        console.print("  [dim]No datasets selected.[/dim]")
        return

    for name in selected:
        download_dataset(name)


@app.command("doctor")
def doctor_cmd(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit machine-readable JSON instead of a table",
    ),
    export: Optional[Path] = typer.Option(
        None,
        "--export",
        help="Write a diagnostics zip (system info, doctor report, redacted config, logs)",
    ),
):
    """Run environment and configuration health checks."""
    from agent.config import Config
    from agent.doctor import run_checks, to_table, to_report, has_errors

    cfg = Config.load()
    checks = run_checks(cfg, session=Session(config=cfg, mode="batch"))
    if export is not None:
        from _version import __version__
        from agent.diagnostics import build_diagnostics_zip

        data, default_name = build_diagnostics_zip(
            version=__version__,
            doctor_report=to_report(checks),
        )
        out = export.expanduser()
        if out.is_dir() or str(out).endswith(("/", "\\")):
            out = out / default_name
        elif out.suffix.lower() != ".zip":
            out = out.with_suffix(".zip")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        console.print(f"  [green]Wrote diagnostics bundle:[/green] {out}")

    if json_output:
        import json

        console.print_json(json.dumps(to_report(checks)))
    else:
        console.print(to_table(checks))

    if has_errors(checks):
        if not json_output:
            console.print(
                "\n[red]Blocking issues found.[/red] Fix errors above, then rerun `fastfold doctor`."
            )
        raise typer.Exit(code=1)

    if not json_output:
        console.print("\n[green]No blocking issues found.[/green]")


# ─── Data subcommand ──────────────────────────────────────────

data_app = typer.Typer(help="Manage local datasets")
app.add_typer(data_app, name="data")


@data_app.command("pull")
def data_pull(
    dataset: str = typer.Argument(
        help="Dataset to download, or 'all' for every auto-downloadable dataset "
        "(depmap, msigdb, string, prism, l1000, alphafold)"
    ),
    output: Optional[Path] = typer.Option(None, help="Output directory"),
):
    """Download a dataset for local use (use 'all' to fetch everything auto-downloadable)."""
    from data.downloader import download_dataset

    download_dataset(dataset, output)


@data_app.command("pull-all")
def data_pull_all(
    output: Optional[Path] = typer.Option(None, help="Output directory"),
):
    """Download every auto-downloadable dataset (depmap, msigdb, string)."""
    from data.downloader import download_all

    download_all(output)


@data_app.command("list")
def data_list():
    """List all known datasets (description, size, download mode)."""
    from data.downloader import dataset_catalog

    console.print(dataset_catalog())


@data_app.command("status")
def data_status():
    """Show download status of local datasets."""
    from data.downloader import dataset_status

    console.print(dataset_status())


# ─── Tool subcommands (direct tool access) ────────────────────

tool_app = typer.Typer(help="Run individual tools directly")
app.add_typer(tool_app, name="tool")


@tool_app.command("list")
def tool_list():
    """List all available tools."""
    from tools import registry, ensure_loaded, tool_load_errors

    ensure_loaded()
    console.print(registry.list_tools_table())
    errors = tool_load_errors()
    if errors:
        names = ", ".join(sorted(errors.keys())[:8])
        extra = "" if len(errors) <= 8 else f" (+{len(errors) - 8} more)"
        console.print(
            f"[yellow]Warning:[/yellow] {len(errors)} tool module(s) failed to load: {names}{extra}"
        )


# ─── Skill subcommands ────────────────────────────────────────

skill_app = typer.Typer(help="Manage and inspect agent skills")
app.add_typer(skill_app, name="skills")
app.add_typer(skill_app, name="skill")  # back-compat alias


@skill_app.command("list")
def skill_list():
    """List all loaded agent skills."""
    from rich.table import Table
    from agent.skills import list_skills, display_author, display_updated, display_version

    skills = list_skills()
    if not skills:
        console.print("[yellow]No skills loaded.[/yellow]")
        raise typer.Exit()

    enabled_count = len([info for info in skills if getattr(info, "enabled", True)])
    table = Table(
        title=f"Agent Skills ({len(skills)} total, {enabled_count} enabled)",
        show_lines=False,
    )
    table.add_column("Skill", style="bold cyan", no_wrap=True)
    table.add_column("Enabled", style="dim", no_wrap=True)
    table.add_column("Source", style="dim")
    table.add_column("Author", style="dim")
    table.add_column("Updated", style="dim")
    table.add_column("Version", style="dim")
    table.add_column("Description", style="white")

    for info in skills:
        table.add_row(
            info.name,
            "yes" if getattr(info, "enabled", True) else "no",
            info.source,
            display_author(info),
            display_updated(info),
            display_version(info),
            info.description,
        )

    console.print(table)


@skill_app.command("enable")
def skill_enable(
    name: str = typer.Argument(..., help="Installed skill name to enable"),
):
    """Enable a skill without uninstalling it."""
    from agent.skills import set_skill_enabled

    result = set_skill_enabled(name, True)
    if result.get("ok"):
        console.print(f"  [green]{result['summary']}[/green]")
    else:
        console.print(f"  [yellow]{result['summary']}[/yellow]")
        raise typer.Exit(code=1)


@skill_app.command("disable")
def skill_disable(
    name: str = typer.Argument(..., help="Installed skill name to disable"),
):
    """Disable a skill without uninstalling it."""
    from agent.skills import set_skill_enabled

    result = set_skill_enabled(name, False)
    if result.get("ok"):
        console.print(f"  [green]{result['summary']}[/green]")
    else:
        console.print(f"  [yellow]{result['summary']}[/yellow]")
        raise typer.Exit(code=1)


@skill_app.command("add")
def skill_add(
    source: str = typer.Argument(
        ..., help="GitHub URL, owner/repo@subpath, local path, or catalog name"
    ),
):
    """Install an agent skill from GitHub, a local path, or the catalog."""
    from agent.skills import install_skill

    provider = _provider_label_for_source(source)
    with console.status(
        f"[green]Installing skill from {source} ({provider})...[/green]", spinner="dots"
    ):
        result = install_skill(source)
    method = {"npx": "npx skills add", "git": "git", "local": "local copy"}.get(result.get("via", ""), result.get("via", "?"))
    if result.get("ok"):
        console.print(f"  [green]{result['summary']}[/green] [dim](provider: {provider}, method: {method})[/dim]")
    else:
        console.print(f"  [red]{result['summary']}[/red]")
        raise typer.Exit(code=1)


@skill_app.command("install")
def skill_install(
    source: str = typer.Argument(..., help="GitHub URL, owner/repo@subpath, local path, or name"),
):
    """Alias for `skills add`."""
    skill_add(source)


@skill_app.command("upgrade")
def skill_upgrade(
    catalog_only: bool = typer.Option(
        False, "--catalog-only", help="Only sync the Fastfold catalog (skip other installed sources)"
    ),
    no_catalog: bool = typer.Option(
        False, "--no-catalog", help="Only update already-installed skills (skip catalog sync)"
    ),
    no_npx: bool = typer.Option(
        False, "--no-npx", help="Skip re-syncing npx-installed (project-local) skills"
    ),
):
    """Sync skills: refresh the Fastfold catalog (add new + update) and re-install tracked skills."""
    from agent.skills import upgrade_skills, GLOBAL_SKILLS_DIR

    if catalog_only and no_catalog:
        console.print("  [red]--catalog-only and --no-catalog are mutually exclusive.[/red]")
        raise typer.Exit(code=2)

    if catalog_only:
        # Catalog sync only.
        from agent.skills import install_skill, DEFAULT_CATALOG

        with console.status("[green]Syncing Fastfold catalog...[/green]", spinner="dots"):
            result = install_skill(DEFAULT_CATALOG.split("@", 1)[0])
        if result.get("ok"):
            console.print(f"  [green]{result['summary']}[/green]")
        else:
            console.print(f"  [red]{result['summary']}[/red]")
            raise typer.Exit(code=1)
        return

    with console.status("[green]Syncing agent skills...[/green]", spinner="dots") as status:
        result = upgrade_skills(
            include_catalog=not no_catalog,
            include_npx=not no_npx,
            progress=lambda msg: status.update(f"[green]{msg}[/green]"),
        )
    if result["added"]:
        console.print(f"  [green]Added:[/green] {', '.join(result['added'])}")
    if result["updated"]:
        console.print(f"  [green]Updated:[/green] {', '.join(result['updated'])}")
    if result.get("npx_synced"):
        console.print(f"  [green]npx-synced:[/green] {result['npx_synced']} project-local source(s)")
    if result["failed"]:
        for source, reason in result["failed"]:
            console.print(f"  [yellow]Failed:[/yellow] {source} — {reason}")
    console.print(f"  [dim]{result['summary']}[/dim]")
    console.print(f"  [dim]Location: {GLOBAL_SKILLS_DIR}[/dim]")


@skill_app.command("remove")
def skill_remove(
    name: str = typer.Argument(..., help="Installed skill name to remove"),
):
    """Remove a globally-installed agent skill."""
    from agent.skills import remove_skill

    result = remove_skill(name)
    if result.get("ok"):
        console.print(f"  [green]{result['summary']}[/green]")
    else:
        console.print(f"  [yellow]{result['summary']}[/yellow]")
        raise typer.Exit(code=1)


@skill_app.command("delete")
def skill_delete(
    name: Optional[str] = typer.Argument(None, help="Skill name to delete (omit when using --all)"),
    all_skills: bool = typer.Option(False, "--all", help="Delete ALL user-installed skills"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt"),
):
    """Delete a skill, or all user-installed skills with --all (asks to confirm first)."""
    from agent.skills import user_installed_skill_names, remove_all_skills, remove_skill

    if not all_skills:
        if not name:
            console.print("  [yellow]Specify a skill name, or use --all to remove everything.[/yellow]")
            raise typer.Exit(code=2)
        result = remove_skill(name)
        style = "green" if result.get("ok") else "yellow"
        console.print(f"  [{style}]{result['summary']}[/{style}]")
        if not result.get("ok"):
            raise typer.Exit(code=1)
        return

    names = user_installed_skill_names()
    if not names:
        console.print("  [dim]No user-installed skills to delete.[/dim] [dim](Bundled skills are kept.)[/dim]")
        return

    console.print(
        f"  [yellow]This will remove {len(names)} user-installed skill(s):[/yellow] {', '.join(names)}"
    )
    console.print("  [dim]Bundled skills (find_skills, skill_creator) are not affected.[/dim]")
    if not yes:
        try:
            confirm = input("  Delete ALL of these skills? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Cancelled.[/dim]")
            raise typer.Exit()
        if confirm not in ("y", "yes"):
            console.print("  [dim]Cancelled.[/dim]")
            return

    result = remove_all_skills()
    console.print(f"  [green]{result['summary']}[/green]")
    if result.get("removed"):
        console.print(f"  [dim]Removed: {', '.join(result['removed'])}[/dim]")


@skill_app.command("find")
def skill_find(
    query: Optional[str] = typer.Argument(None, help="Optional search query"),
):
    """Discover installable skills from the catalog."""
    from rich.table import Table
    from agent.skills import discover_skills

    with spinner("Searching skill catalog..."):
        results = discover_skills(query)
    if not results:
        console.print(
            "  [yellow]No matching skills found.[/yellow] "
            "[dim](Requires git; check network/catalog access.)[/dim]"
        )
        raise typer.Exit()

    table = Table(title=f"Available Skills ({len(results)})", show_lines=False)
    table.add_column("Skill", style="bold cyan", no_wrap=True)
    table.add_column("Install source", style="dim")
    table.add_column("Description", style="white")
    for r in results:
        table.add_row(r["name"], r["install_source"], r["description"])
    console.print(table)
    console.print("  [dim]Install with:[/dim] fastfold skills add <install source>")


@skill_app.command("info")
def skill_info_cmd(
    name: str = typer.Argument(..., help="Skill name"),
):
    """Show details for an installed skill."""
    from agent.skills import skill_info

    info = skill_info(name)
    if not info:
        console.print(f"  [yellow]Skill '{name}' is not installed.[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"  [bold cyan]{info.name}[/bold cyan] [dim]({info.source})[/dim]")
    if info.description:
        console.print(f"  {info.description}")
    if info.tags:
        console.print(f"  [dim]tags:[/dim] {', '.join(info.tags)}")
    if info.path:
        console.print(f"  [dim]path:[/dim] {info.path}")


# ─── Top-level `add` group (alias: `fastfold add skill <source>`) ─────────────
add_app = typer.Typer(help="Add skills and other resources")
app.add_typer(add_app, name="add")


@add_app.command("skills")
def add_skills_cmd(
    source: str = typer.Argument(..., help="GitHub URL, owner/repo@subpath, local path, or name"),
):
    """Install an agent skill (alias for ``fastfold skills add``)."""
    skill_add(source)


@add_app.command("skill", hidden=True)
def add_skill_cmd(
    source: str = typer.Argument(..., help="GitHub URL, owner/repo@subpath, local path, or name"),
):
    """Back-compat alias for `fastfold add skills`."""
    skill_add(source)


# ─── Knowledge subcommands ────────────────────────────────────

knowledge_app = typer.Typer(help="Manage knowledge substrate, ingestion, and quality gates")
app.add_typer(knowledge_app, name="knowledge")


# ─── Trace subcommands ────────────────────────────────────────

trace_app = typer.Typer(help="Inspect and diagnose execution traces")
app.add_typer(trace_app, name="trace")


def _latest_trace_path() -> Optional[Path]:
    from agent.trace import TraceLogger

    traces_dir = TraceLogger.traces_dir()
    traces = list(traces_dir.glob("*.trace.jsonl"))
    if not traces:
        return None
    return max(traces, key=lambda p: p.stat().st_mtime)


def _resolve_trace_path(path: Optional[Path], session_id: Optional[str]) -> Optional[Path]:
    from agent.trace import TraceLogger

    if path is not None and session_id is not None:
        console.print("[red]Use either --path or --session-id, not both.[/red]")
        raise typer.Exit(code=2)

    if path is not None:
        return path
    if session_id:
        return TraceLogger.traces_dir() / f"{session_id}.trace.jsonl"
    return _latest_trace_path()


def _latest_report_path(output_base: Optional[str] = None) -> Optional[Path]:
    reports_dir = (
        Path(output_base) / "reports" if output_base else Path.cwd() / "outputs" / "reports"
    )
    if not reports_dir.exists():
        return None
    reports = list(reports_dir.glob("*.md"))
    if not reports:
        return None
    return max(reports, key=lambda p: p.stat().st_mtime)


def _trace_has_issues(diag: dict) -> bool:
    return any(
        (
            diag.get("unclosed_queries"),
            diag.get("queries_with_no_plan"),
            diag.get("queries_with_no_completion"),
            diag.get("queries_with_synthesis_mismatch"),
        )
    )


def _print_trace_diagnostics_table(diag: dict, title: str):
    table = Table(title=title)
    table.add_column("Metric", style="cyan")
    table.add_column("Value")
    table.add_row("Session", diag.get("session_id", "(unknown)") or "(unknown)")
    table.add_row("Events", str(diag.get("event_count", 0)))
    table.add_row("Queries", str(diag.get("query_count", 0)))
    table.add_row(
        "Query starts / ends",
        f"{diag.get('query_start_count', 0)} / {diag.get('query_end_count', 0)}",
    )
    table.add_row("Step starts", str(diag.get("total_step_start_count", 0)))
    table.add_row("Step completes", str(diag.get("total_step_complete_count", 0)))
    table.add_row("Step fails", str(diag.get("total_step_fail_count", 0)))
    table.add_row("Step retries", str(diag.get("total_step_retry_count", 0)))
    table.add_row("Unclosed queries", str(diag.get("unclosed_queries", [])))
    table.add_row("Queries with failures", str(diag.get("queries_with_failures", [])))
    table.add_row("Queries with no plan", str(diag.get("queries_with_no_plan", [])))
    table.add_row(
        "Queries with no completion",
        str(diag.get("queries_with_no_completion", [])),
    )
    table.add_row(
        "Synthesis mismatches",
        str(diag.get("queries_with_synthesis_mismatch", [])),
    )
    console.print(table)


def _run_step_command(label: str, cmd: list[str], env: Optional[dict] = None) -> bool:
    console.print(f"\n[bold cyan]{label}[/bold cyan]")
    console.print(f"[dim]$ {' '.join(cmd)}[/dim]")
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if stdout:
        console.print(stdout)
    if stderr:
        style = "yellow" if proc.returncode == 0 else "red"
        console.print(stderr, style=style)
    if proc.returncode == 0:
        console.print(f"[green]PASS[/green] {label}")
        return True
    console.print(f"[red]FAIL[/red] {label} (exit={proc.returncode})")
    return False


@trace_app.command("diagnose")
def trace_diagnose(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Path to a trace JSONL file"),
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        "-s",
        help="Session ID (looks up ~/.fastfold-cli/traces/<id>.trace.jsonl)",
    ),
    as_json: bool = typer.Option(False, "--json", help="Print diagnostics as JSON"),
    show_queries: bool = typer.Option(
        False, "--show-queries", help="Show per-query diagnostics table"
    ),
    strict: bool = typer.Option(
        False, "--strict", help="Exit non-zero if health issues are detected"
    ),
):
    """Diagnose trace health (query integrity, failures, synthesis lifecycle)."""
    from agent.trace import TraceLogger

    trace_path = _resolve_trace_path(path, session_id)
    if trace_path is None:
        console.print("[yellow]No trace files found in ~/.fastfold-cli/traces[/yellow]")
        raise typer.Exit(code=2)
    if not trace_path.exists():
        console.print(f"[red]Trace file not found:[/red] {trace_path}")
        raise typer.Exit(code=2)

    trace = TraceLogger.load(trace_path)
    diag = trace.diagnostics()

    if as_json:
        console.print_json(data=diag)
    else:
        _print_trace_diagnostics_table(diag, title=f"Trace Diagnostics: {trace_path.name}")

        if show_queries:
            q_table = Table(title="Per-Query Diagnostics")
            q_table.add_column("#", style="cyan")
            q_table.add_column("Closed")
            q_table.add_column("Plans")
            q_table.add_column("Step OK")
            q_table.add_column("Step Fail")
            q_table.add_column("Retries")
            q_table.add_column("Synth start/end")
            q_table.add_column("Query")
            for q in diag["queries"]:
                q_table.add_row(
                    str(q["query_number"]),
                    "yes" if q["closed"] else "no",
                    str(q["plan_count"]),
                    str(q["step_complete_count"]),
                    str(q["step_fail_count"]),
                    str(q["step_retry_count"]),
                    f"{q['synthesize_start_count']}/{q['synthesize_end_count']}",
                    (q["query"] or "")[:80],
                )
            console.print(q_table)

    has_issues = _trace_has_issues(diag)
    if strict and has_issues:
        raise typer.Exit(code=2)


@trace_app.command("export")
def trace_export(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Path to a trace JSONL file"),
    session_id: Optional[str] = typer.Option(
        None,
        "--session-id",
        "-s",
        help="Session ID (looks up ~/.fastfold-cli/traces/<id>.trace.jsonl)",
    ),
    report: Optional[Path] = typer.Option(
        None, "--report", "-r", help="Optional markdown report to include"
    ),
    out_dir: Optional[Path] = typer.Option(
        None, "--out-dir", help="Bundle output directory (default: ~/.fastfold-cli/exports)"
    ),
    zip_bundle: bool = typer.Option(True, "--zip/--no-zip", help="Also produce a zip archive"),
):
    """Export a reproducible run bundle (trace, diagnostics, report, metadata)."""
    from agent.config import Config
    from agent.trace import TraceLogger
    from agent.trajectory import Trajectory

    trace_path = _resolve_trace_path(path, session_id)
    if trace_path is None:
        console.print("[yellow]No trace files found in ~/.fastfold-cli/traces[/yellow]")
        raise typer.Exit(code=2)
    if not trace_path.exists():
        console.print(f"[red]Trace file not found:[/red] {trace_path}")
        raise typer.Exit(code=2)

    trace = TraceLogger.load(trace_path)
    diag = trace.diagnostics()

    cfg = Config.load()
    resolved_report = report
    if resolved_report is None:
        resolved_report = _latest_report_path(cfg.get("sandbox.output_dir"))
    if resolved_report is not None and not resolved_report.exists():
        console.print(f"[red]Report file not found:[/red] {resolved_report}")
        raise typer.Exit(code=2)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = out_dir or (Path.home() / ".fastfold-cli" / "exports")
    bundle_dir = base / f"ct_run_bundle_{trace.session_id or 'session'}_{ts}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    trace_copy = bundle_dir / "trace.jsonl"
    shutil.copy2(trace_path, trace_copy)
    (bundle_dir / "trace.txt").write_text(trace.to_text(), encoding="utf-8")
    (bundle_dir / "trace_diagnostics.json").write_text(
        json.dumps(diag, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (bundle_dir / "query_summaries.json").write_text(
        json.dumps(trace.query_summaries(), indent=2),
        encoding="utf-8",
    )

    copied_report = None
    if resolved_report is not None:
        copied_report = bundle_dir / "report.md"
        shutil.copy2(resolved_report, copied_report)

    copied_session = None
    session_file = None
    if trace.session_id:
        session_file = Trajectory.sessions_dir() / f"{trace.session_id}.jsonl"
    if session_file is not None and session_file.exists():
        copied_session = bundle_dir / "session.jsonl"
        shutil.copy2(session_file, copied_session)

    manifest = {
        "generated_at_utc": ts,
        "session_id": trace.session_id,
        "source_trace": str(trace_path),
        "included_files": {
            "trace_jsonl": str(trace_copy),
            "trace_txt": str(bundle_dir / "trace.txt"),
            "trace_diagnostics_json": str(bundle_dir / "trace_diagnostics.json"),
            "query_summaries_json": str(bundle_dir / "query_summaries.json"),
            "report_md": str(copied_report) if copied_report else None,
            "session_jsonl": str(copied_session) if copied_session else None,
        },
        "note": (
            "If report was auto-selected, it is the latest markdown report by mtime "
            "from sandbox.output_dir/reports."
            if report is None
            else "Report path explicitly provided."
        ),
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    console.print(f"[green]Bundle exported:[/green] {bundle_dir}")
    if copied_report:
        console.print(f"[dim]Included report:[/dim] {resolved_report}")
    else:
        console.print("[yellow]No report included (none found/provided).[/yellow]")

    if zip_bundle:
        archive = shutil.make_archive(str(bundle_dir), "zip", root_dir=bundle_dir)
        console.print(f"[green]Zip archive:[/green] {archive}")


@app.command("release-check")
def release_check_cmd(
    run_tests: bool = typer.Option(
        True, "--tests/--no-tests", help="Run local pytest regression suite"
    ),
    run_benchmark: bool = typer.Option(
        True, "--benchmark/--no-benchmark", help="Run strict knowledge benchmark gate"
    ),
    run_trace: bool = typer.Option(
        True, "--trace/--no-trace", help="Run strict diagnostics on latest trace"
    ),
    trace_path: Optional[Path] = typer.Option(
        None, "--trace-path", help="Trace path for diagnostics"
    ),
    trace_required: bool = typer.Option(
        False, "--trace-required", help="Fail if no trace file is found"
    ),
    include_live: bool = typer.Option(
        False, "--live", help="Also run live API smoke + live E2E prompt matrix"
    ),
    matrix_limit: int = typer.Option(10, "--matrix-limit", help="Prompt limit for live E2E matrix"),
    matrix_strict: bool = typer.Option(
        True,
        "--matrix-strict/--no-matrix-strict",
        help="Enable strict assertions in live E2E matrix",
    ),
    matrix_max_failed: int = typer.Option(
        1, "--matrix-max-failed", help="Max failed prompts allowed in strict matrix mode"
    ),
    require_profile: Optional[str] = typer.Option(
        None, "--require-profile", help="Require agent.profile to match (e.g. pharma)"
    ),
    pharma: bool = typer.Option(False, "--pharma", help="Enforce pharma deployment policy checks"),
):
    """Run a production release gate: doctor + tests + benchmark + trace diagnostics."""
    from agent.config import Config
    from agent.doctor import has_errors, run_checks, to_table
    from agent.trace import TraceLogger
    from kb.benchmarks import BenchmarkSuite

    failed = False

    console.print("\n[bold]Release Check[/bold]")

    cfg = Config.load()
    if pharma and not require_profile:
        require_profile = "pharma"

    if require_profile:
        expected = require_profile.strip().lower()
        actual = str(cfg.get("agent.profile", "research")).strip().lower()
        if actual != expected:
            console.print(f"[red]Profile mismatch:[/red] expected '{expected}', got '{actual}'.")
            failed = True

    if pharma:
        policy_issues = []
        if str(cfg.get("agent.synthesis_style", "standard")).strip().lower() != "pharma":
            policy_issues.append("agent.synthesis_style must be 'pharma'")
        if not bool(cfg.get("agent.quality_gate_strict", False)):
            policy_issues.append("agent.quality_gate_strict must be true")
        if bool(cfg.get("agent.enable_experimental_tools", False)):
            policy_issues.append("agent.enable_experimental_tools must be false")
        if bool(cfg.get("agent.enable_claude_code_tool", False)):
            policy_issues.append("agent.enable_claude_code_tool must be false")
        if policy_issues:
            console.print("[red]Pharma policy checks failed:[/red]")
            for issue in policy_issues:
                console.print(f"- {issue}")
            failed = True

    checks = run_checks(cfg)
    console.print(to_table(checks))
    if has_errors(checks):
        console.print("[red]Doctor checks have blocking errors.[/red]")
        failed = True

    if run_tests:
        ok = _run_step_command(
            "Local test suite",
            ["pytest", "-q", "tests", "-m", "not data_smoke and not e2e and not e2e_matrix"],
        )
        failed = failed or (not ok)

    if run_benchmark:
        suite = BenchmarkSuite.load()
        summary = suite.run()
        gate = suite.gate(summary, min_pass_rate=0.9)

        table = Table(title="Release Benchmark Gate")
        table.add_column("Metric", style="cyan")
        table.add_column("Value")
        table.add_row("Total cases", str(summary["total_cases"]))
        table.add_row("Expected behavior matches", str(summary["expected_behavior_matches"]))
        table.add_row("Pass rate", str(summary["pass_rate"]))
        table.add_row("Gate", gate["message"])
        console.print(table)

        if not gate["ok"]:
            console.print("[red]Benchmark release gate failed.[/red]")
            failed = True

    if run_trace:
        resolved_trace = trace_path or _latest_trace_path()
        if resolved_trace is None or not resolved_trace.exists():
            msg = "No trace file found for diagnostics."
            if trace_required:
                console.print(f"[red]{msg}[/red]")
                failed = True
            else:
                console.print(f"[yellow]{msg}[/yellow]")
        else:
            trace = TraceLogger.load(resolved_trace)
            diag = trace.diagnostics()
            _print_trace_diagnostics_table(diag, title=f"Trace Diagnostics: {resolved_trace.name}")
            if _trace_has_issues(diag):
                console.print("[red]Trace diagnostics detected integrity issues.[/red]")
                failed = True

    if include_live:
        smoke_env = dict(os.environ)
        smoke_env["RUN_DATA_SMOKE"] = "1"
        smoke_env.setdefault("DATA_SMOKE_STRICT", "1")
        smoke_ok = _run_step_command(
            "Live data source smoke checks",
            ["pytest", "-q", "tests/test_api_smoke.py"],
            env=smoke_env,
        )
        failed = failed or (not smoke_ok)

        matrix_env = dict(os.environ)
        matrix_env["RUN_E2E_MATRIX"] = "1"
        matrix_env["E2E_MATRIX_LIMIT"] = str(max(1, matrix_limit))
        matrix_env["E2E_MATRIX_STRICT"] = "1" if matrix_strict else "0"
        matrix_env["E2E_MATRIX_MAX_FAILED_QUERIES"] = str(max(0, matrix_max_failed))
        matrix_ok = _run_step_command(
            "Live E2E prompt matrix",
            ["pytest", "-q", "tests/test_e2e_matrix.py", "--run-e2e"],
            env=matrix_env,
        )
        failed = failed or (not matrix_ok)

    if failed:
        console.print("\n[red]Release check failed.[/red]")
        raise typer.Exit(code=2)

    console.print("\n[green]Release check passed.[/green]")


@knowledge_app.command("status")
def knowledge_status():
    """Show knowledge substrate status."""
    from kb.substrate import KnowledgeSubstrate

    substrate = KnowledgeSubstrate()
    summary = substrate.summary()
    table = Table(title="Knowledge Substrate")
    table.add_column("Metric", style="cyan")
    table.add_column("Value")
    table.add_row("Path", summary["path"])
    table.add_row("Schema Version", str(summary["schema_version"]))
    table.add_row("Entities", str(summary["n_entities"]))
    table.add_row("Relations", str(summary["n_relations"]))
    table.add_row("Evidence", str(summary["n_evidence"]))
    for et, count in sorted(summary.get("entity_types", {}).items()):
        table.add_row(f"entity_type:{et}", str(count))
    console.print(table)


@knowledge_app.command("ingest")
def knowledge_ingest(
    source: str = typer.Argument(
        ..., help="Source: evidence_store | pubmed | openalex | opentargets"
    ),
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Query for API sources"),
    max_results: int = typer.Option(10, "--max-results", help="Max records for API sources"),
    scan_limit: int = typer.Option(1000, "--scan-limit", help="Max local evidence rows to scan"),
):
    """Ingest knowledge into canonical substrate."""
    from kb.ingest import KnowledgeIngestionPipeline

    pipeline = KnowledgeIngestionPipeline()
    result = pipeline.ingest(
        source=source,
        query=query,
        max_results=max_results,
        scan_limit=scan_limit,
    )
    if result.get("error"):
        console.print(f"[red]{result['error']}[/red]")
        raise typer.Exit(code=2)
    console.print(result.get("summary", "Ingestion completed."))


@knowledge_app.command("search")
def knowledge_search(
    query: str = typer.Argument(..., help="Search text"),
    limit: int = typer.Option(20, "--limit", help="Maximum entities to return"),
):
    """Search canonical entities."""
    from kb.substrate import KnowledgeSubstrate

    substrate = KnowledgeSubstrate()
    entities = substrate.search_entities(query, limit=limit)
    table = Table(title=f"Knowledge Search: {query}")
    table.add_column("Entity ID", style="cyan")
    table.add_column("Type")
    table.add_column("Name")
    table.add_column("Synonyms", style="dim")
    for entity in entities:
        table.add_row(entity.id, entity.entity_type, entity.name, ", ".join(entity.synonyms[:4]))
    console.print(table)


@knowledge_app.command("related")
def knowledge_related(
    entity_id: str = typer.Argument(..., help="Canonical entity id (e.g., gene:TP53)"),
    predicate: Optional[str] = typer.Option(None, "--predicate", help="Filter predicate"),
    limit: int = typer.Option(20, "--limit", help="Maximum relations"),
):
    """Show related entities for an entity."""
    from kb.substrate import KnowledgeSubstrate

    substrate = KnowledgeSubstrate()
    rows = substrate.related_entities(entity_id, predicate=predicate, limit=limit)
    table = Table(title=f"Related Entities: {entity_id}")
    table.add_column("Predicate", style="cyan")
    table.add_column("Other Entity")
    table.add_column("Support")
    table.add_column("Contradict")
    table.add_column("Avg Score")
    for row in rows:
        table.add_row(
            row["predicate"],
            row["other_entity_id"],
            str(row["support_claims"]),
            str(row["contradict_claims"]),
            str(row["average_claim_score"]),
        )
    console.print(table)


@knowledge_app.command("rank")
def knowledge_rank(
    entity_id: Optional[str] = typer.Option(None, "--entity-id", help="Entity id filter"),
    predicate: Optional[str] = typer.Option(None, "--predicate", help="Predicate filter"),
    limit: int = typer.Option(20, "--limit", help="Maximum relations"),
):
    """Rank relations by evidence strength."""
    from kb.reasoning import EvidenceReasoner
    from kb.substrate import KnowledgeSubstrate

    reasoner = EvidenceReasoner(KnowledgeSubstrate())
    rows = reasoner.rank_relations(entity_id=entity_id, predicate=predicate, limit=limit)
    table = Table(title="Ranked Relations")
    table.add_column("Relation", style="cyan")
    table.add_column("Score")
    table.add_column("Claims")
    for row in rows:
        relation = f"{row['subject_id']} --{row['predicate']}--> {row['object_id']}"
        table.add_row(relation, str(row["score"]), str(row["n_claims"]))
    console.print(table)


@knowledge_app.command("contradictions")
def knowledge_contradictions(
    entity_id: Optional[str] = typer.Option(None, "--entity-id", help="Entity id filter"),
    predicate: Optional[str] = typer.Option(None, "--predicate", help="Predicate filter"),
):
    """Detect contradictory evidence clusters."""
    from kb.reasoning import EvidenceReasoner
    from kb.substrate import KnowledgeSubstrate

    reasoner = EvidenceReasoner(KnowledgeSubstrate())
    rows = reasoner.detect_contradictions(entity_id=entity_id, predicate=predicate)
    table = Table(title="Contradictions")
    table.add_column("Relation", style="cyan")
    table.add_column("Support")
    table.add_column("Contradict")
    table.add_column("Support Score")
    table.add_column("Contradict Score")
    for row in rows:
        relation = f"{row['subject_id']} --{row['predicate']}--> {row['object_id']}"
        table.add_row(
            relation,
            str(row["support_claims"]),
            str(row["contradict_claims"]),
            str(row["support_score"]),
            str(row["contradict_score"]),
        )
    console.print(table)


@knowledge_app.command("schema-check")
def knowledge_schema_check():
    """Run schema drift checks against external integration baselines."""
    from kb.schema_monitor import SchemaMonitor

    monitor = SchemaMonitor()
    results = monitor.check()
    summary = monitor.summarize(results)
    table = Table(title="Schema Drift Monitor")
    table.add_column("Monitor", style="cyan")
    table.add_column("Status")
    table.add_column("Added")
    table.add_column("Removed")
    table.add_column("Error")
    for row in summary["results"]:
        table.add_row(
            row["monitor"],
            row["status"],
            str(len(row["added_paths"])),
            str(len(row["removed_paths"])),
            row.get("error", ""),
        )
    console.print(table)
    if summary["counts"].get("drift", 0) > 0 or summary["counts"].get("error", 0) > 0:
        raise typer.Exit(code=2)


@knowledge_app.command("schema-update")
def knowledge_schema_update(
    monitor: Optional[str] = typer.Option(None, "--monitor", help="Single monitor to update"),
):
    """Update schema drift baselines from current responses."""
    from kb.schema_monitor import SchemaMonitor

    mon = SchemaMonitor()
    results = mon.update_baseline(monitor=monitor)
    summary = mon.summarize(results)
    console.print(f"Updated schema baseline for {summary['total']} monitor(s).")


@knowledge_app.command("benchmark")
def knowledge_benchmark(
    min_pass_rate: float = typer.Option(0.9, "--min-pass-rate", help="Release gate threshold"),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero if gate fails"),
):
    """Run benchmark suite and evaluate release gate."""
    from kb.benchmarks import BenchmarkSuite

    suite = BenchmarkSuite.load()
    summary = suite.run()
    gate = suite.gate(summary, min_pass_rate=min_pass_rate)

    table = Table(title="Knowledge Benchmarks")
    table.add_column("Metric", style="cyan")
    table.add_column("Value")
    table.add_row("Total cases", str(summary["total_cases"]))
    table.add_row("Expected behavior matches", str(summary["expected_behavior_matches"]))
    table.add_row("Pass rate", str(summary["pass_rate"]))
    table.add_row("Gate", gate["message"])
    console.print(table)
    if strict and not gate["ok"]:
        raise typer.Exit(code=2)


# ─── Report subcommands ──────────────────────────────────────

report_app = typer.Typer(help="Generate and publish reports")
app.add_typer(report_app, name="report")


@report_app.command("list")
def report_list():
    """List available markdown reports."""
    from agent.config import Config

    cfg = Config.load()
    reports_dir = (
        Path(cfg.get("sandbox.output_dir")) / "reports"
        if cfg.get("sandbox.output_dir")
        else Path.cwd() / "outputs" / "reports"
    )
    if not reports_dir.exists():
        console.print("[dim]No reports directory found.[/dim]")
        raise typer.Exit()

    reports = sorted(reports_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not reports:
        console.print("[dim]No reports found.[/dim]")
        raise typer.Exit()

    table = Table(title="Reports")
    table.add_column("#", style="dim")
    table.add_column("File", style="cyan")
    table.add_column("Size", style="dim")
    table.add_column("Modified")
    for i, r in enumerate(reports[:20], 1):
        size = r.stat().st_size
        size_str = f"{size / 1024:.1f}K" if size > 1024 else f"{size}B"
        mtime = datetime.fromtimestamp(r.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        table.add_row(str(i), r.name, size_str, mtime)
    console.print(table)


@report_app.command("publish")
def report_publish(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="Markdown report to convert"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output HTML path"),
):
    """Convert a markdown report to a shareable HTML page."""
    from agent.config import Config
    from reports.html import publish_report

    if path is None:
        cfg = Config.load()
        path = _latest_report_path(cfg.get("sandbox.output_dir"))
        if path is None:
            console.print("[yellow]No reports found. Run a query first.[/yellow]")
            raise typer.Exit(code=2)

    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}")
        raise typer.Exit(code=2)

    result = publish_report(path, out_path=out)
    console.print(f"[green]Published:[/green] {result}")


@report_app.command("show")
def report_show(
    path: Optional[Path] = typer.Option(None, "--path", "-p", help="HTML report to open"),
):
    """Open an HTML report in the default browser."""
    import webbrowser

    from agent.config import Config
    from reports.html import publish_report

    if path is None:
        cfg = Config.load()
        md_path = _latest_report_path(cfg.get("sandbox.output_dir"))
        if md_path is None:
            console.print("[yellow]No reports found.[/yellow]")
            raise typer.Exit(code=2)
        html_path = md_path.with_suffix(".html")
        if not html_path.exists():
            html_path = publish_report(md_path)
            console.print(f"[dim]Auto-published: {html_path}[/dim]")
        path = html_path

    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}")
        raise typer.Exit(code=2)

    webbrowser.open(f"file://{path.resolve()}")
    console.print(f"[green]Opened in browser:[/green] {path}")


@report_app.command("notebook")
def report_notebook(
    session: Optional[str] = typer.Option(
        None, "--session", "-s", help="Session ID (prefix or full). Default: most recent"
    ),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Output notebook path"),
    html: bool = typer.Option(False, "--html", help="Also export as HTML"),
):
    """Export an agent trace as a Jupyter notebook (.ipynb)."""
    import re
    from agent.trace_store import TraceStore

    # Find trace file
    trace_path = TraceStore.find_trace(session)
    if trace_path is None:
        console.print(
            "[yellow]No trace files found. Run a query first to generate a trace.[/yellow]"
        )
        raise typer.Exit(code=2)

    console.print(f"  [dim]Trace:[/dim] {trace_path.name}")

    # Lazy import nbformat
    try:
        from reports.notebook import trace_to_notebook, save_notebook
    except ImportError:
        console.print("[red]nbformat is required. Install with:[/red] pip install nbformat")
        raise typer.Exit(code=2)

    # Convert trace to notebook
    nb = trace_to_notebook(trace_path)

    # Determine output path
    if out is None:
        from agent.config import Config

        cfg = Config.load()
        reports_dir = (
            Path(cfg.get("sandbox.output_dir")) / "reports"
            if cfg.get("sandbox.output_dir")
            else Path.cwd() / "outputs" / "reports"
        )
        slug = re.sub(r"[^a-zA-Z0-9]+", "_", trace_path.stem.replace(".trace", "")).strip("_")
        out = reports_dir / f"{slug}.ipynb"

    out_path = save_notebook(nb, out)
    console.print(f"  [green]Notebook:[/green] {out_path}")

    # Optional HTML export
    if html:
        try:
            import nbconvert
            from nbconvert import HTMLExporter

            exporter = HTMLExporter()
            html_body, _ = exporter.from_notebook_node(nb)
            html_path = out_path.with_suffix(".html")
            html_path.write_text(html_body, encoding="utf-8")
            console.print(f"  [green]HTML:[/green] {html_path}")
        except ImportError:
            console.print(
                "[yellow]nbconvert not installed. Falling back to markdown-based HTML.[/yellow]\n"
                "  [dim]Install with: pip install nbconvert[/dim]"
            )
            # Fall back to existing HTML renderer on markdown cells
            from reports.html import render_html_report

            md_parts = [c.source for c in nb.cells if c.cell_type == "markdown"]
            md_text = "\n\n".join(md_parts)
            html_content = render_html_report(md_text, title="Fastfold Notebook Export")
            html_path = out_path.with_suffix(".html")
            html_path.write_text(html_content, encoding="utf-8")
            console.print(f"  [green]HTML (markdown only):[/green] {html_path}")


# ─── Case study subcommands ─────────────────────────────────

case_study_app = typer.Typer(help="Run curated drug case studies")
app.add_typer(case_study_app, name="case-study")


@case_study_app.command("list")
def case_study_list():
    """List available curated case studies."""
    from agent.case_studies import CASE_STUDIES

    table = Table(title="Case Studies")
    table.add_column("ID", style="cyan")
    table.add_column("Drug")
    table.add_column("Threads", style="dim")
    table.add_column("Description")
    for case_id, case in CASE_STUDIES.items():
        table.add_row(
            case_id,
            case.name,
            str(len(case.thread_goals)),
            case.description[:80] + ("..." if len(case.description) > 80 else ""),
        )
    console.print(table)


@case_study_app.command("run")
def case_study_run(
    case_id: str = typer.Argument(..., help="Case study ID (e.g., revlimid, gleevec)"),
    threads: Optional[int] = typer.Option(
        None, "--threads", "-t", help="Number of parallel threads"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model to use"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Run a curated drug case study with multi-agent analysis."""
    from agent.case_studies import CASE_STUDIES, run_case_study
    from agent.config import Config
    from reports.html import publish_report

    if case_id not in CASE_STUDIES:
        available = ", ".join(sorted(CASE_STUDIES.keys()))
        console.print(f"[red]Unknown case study '{case_id}'.[/red] Available: {available}")
        raise typer.Exit(code=2)

    cfg = Config.load()
    if model:
        cfg.set("llm.model", model)

    llm_issue = cfg.llm_preflight_issue()
    if llm_issue:
        console.print("\n  [yellow]First-time setup required.[/yellow]\n")
        setup_cmd(api_key=None, openai_api_key=None, fastfold_api_key=None, provider=None)
        cfg = Config.load()
        if model:
            cfg.set("llm.model", model)
        llm_issue = cfg.llm_preflight_issue()
        if llm_issue:
            console.print(f"\n  [red]Setup incomplete:[/red] {llm_issue}")
            raise typer.Exit(code=2)

    session = Session(config=cfg, verbose=verbose)
    case = CASE_STUDIES[case_id]

    print_banner(cfg)
    console.print(
        Panel(
            f"[bold]{case.name}[/bold]\n[dim]{case.description}[/dim]",
            title="[cyan]Case Study[/cyan]",
            border_style="cyan",
        )
    )
    console.print()

    result = run_case_study(session, case_id, n_threads=threads)

    # Auto-publish HTML
    md_path = _latest_report_path(cfg.get("sandbox.output_dir"))
    if md_path:
        html_path = publish_report(md_path)
        console.print(f"\n  [green]HTML report:[/green] {html_path}")

    console.print()


# ─── Main entry point ─────────────────────────────────────────


@app.command("run", hidden=True)
def run_cmd(
    query_parts: list[str] = typer.Argument(None, help="Research question to investigate"),
    smiles: Optional[str] = typer.Option(None, "--smiles", "-s", help="Compound SMILES string"),
    target: Optional[str] = typer.Option(
        None, "--target", "-t", help="Target protein (UniProt ID or gene symbol)"
    ),
    indication: Optional[str] = typer.Option(
        None, "--indication", "-i", help="Cancer type / indication"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for reports"
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model to use"),
    agents: Optional[int] = typer.Option(
        None, "--agents", "-a", help="Run with N parallel research agents"
    ),
    resume: Optional[str] = typer.Option(
        None, "--resume", "-r", help="Resume a previous session (ID or 'last')"
    ),
    continue_last: bool = typer.Option(
        False, "--continue", "-c", help="Continue the most recent session"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    version: bool = typer.Option(False, "--version", "-V", help="Show version"),
):
    """
    Fastfold Agent CLI — Where scientists and AI agents work together doing real science.

    Run without arguments for interactive mode.
    Pass a question for single-query mode.
    """
    if version:
        console.print(f"fastfold v{__version__}")
        raise typer.Exit()

    query = " ".join(query_parts).strip() if query_parts else None

    # Build context from flags
    context = {}
    if smiles:
        context["compound_smiles"] = smiles
    if target:
        context["target"] = target
    if indication:
        context["indication"] = indication

    # Determine session resume
    resume_id = None
    if continue_last:
        resume_id = "last"
    elif resume:
        resume_id = resume

    if query:
        # Single query mode
        run_query(query, context, output, model, verbose, agents=agents)
    else:
        # Interactive mode
        run_interactive(context, output, model, verbose, resume_id=resume_id)


def run_query(
    query: str,
    context: dict,
    output: Optional[Path],
    model: Optional[str],
    verbose: bool,
    agents: Optional[int] = None,
):
    """Execute a single research query."""
    from agent.config import Config

    cfg = Config.load()
    if model:
        cfg.set("llm.model", model)

    llm_issue = cfg.llm_preflight_issue()
    if llm_issue:
        console.print("\n  [yellow]First-time setup required.[/yellow]\n")
        setup_cmd(api_key=None, openai_api_key=None, fastfold_api_key=None, provider=None)
        cfg = Config.load()
        if model:
            cfg.set("llm.model", model)
        llm_issue = cfg.llm_preflight_issue()
        if llm_issue:
            console.print(f"\n  [red]Setup incomplete:[/red] {llm_issue}")
            raise typer.Exit(code=2)

    session = Session(config=cfg, verbose=verbose)

    print_banner(cfg)
    console.print(
        Panel(
            f"[bold]{query}[/bold]",
            title="[cyan]fastfold[/cyan]",
            border_style="cyan",
        )
    )
    console.print()

    # Multi-agent mode
    if agents is not None and agents > 1:
        from agent.orchestrator import ResearchOrchestrator

        orchestrator = ResearchOrchestrator(session, n_threads=agents)
        result = orchestrator.run(query, context)

        if output:
            output.mkdir(parents=True, exist_ok=True)
            report_path = output / "report.md"
            report_path.write_text(result.to_markdown())
            console.print(f"\n  Report saved to {report_path}")

        console.print()
        return

    # Execute via Agent SDK runner (default) or legacy AgentLoop (fallback)
    use_sdk = cfg.get("agent.use_sdk", True)

    if use_sdk:
        from agent.runner import AgentRunner

        agent = AgentRunner(session)
        result = agent.run(query, context)
    else:
        from agent.loop import AgentLoop, ClarificationNeeded

        agent = AgentLoop(session)
        try:
            result = agent.run(query, context)
        except ClarificationNeeded as e:
            console.print(f"\n  [cyan]{e.clarification.question}[/cyan]")
            if e.clarification.suggestions:
                console.print(f"  [dim]e.g. {', '.join(e.clarification.suggestions[:3])}[/dim]")
            console.print(
                f"\n  [dim]Tip: provide context with --smiles, --target, or --indication flags.[/dim]"
            )
            return

    # Output
    if output:
        output.mkdir(parents=True, exist_ok=True)
        report_path = output / "report.md"
        report_path.write_text(result.to_markdown())
        console.print(f"\n  Report saved to {report_path}")

    # Summary already streamed to stdout during synthesis
    console.print()


@app.command("bench")
def bench(
    question: Optional[str] = typer.Option(
        None, "--question", "-q", help="Run a single question by ID"
    ),
    parallel: int = typer.Option(10, "--parallel", "-p", help="Number of parallel workers"),
    timeout: int = typer.Option(300, "--timeout", help="Timeout per question in seconds"),
    max_turns: int = typer.Option(15, "--max-turns", help="Max agentic loop turns"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model override"),
    eval_model: str = typer.Option(
        "claude-sonnet-4-5-20250929", "--eval-model", help="Model for LLM-as-judge evaluation"
    ),
    manifest: str = typer.Option(
        "/mnt/bixbench/manifest.json", "--manifest", help="Path to manifest JSON"
    ),
    output: str = typer.Option("/mnt/bixbench/outputs", "--output", "-o", help="Output directory"),
    only_failed: bool = typer.Option(False, "--only-failed", help="Re-run only failed questions"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview questions without executing"),
    no_eval: bool = typer.Option(False, "--no-eval", help="Skip inline LLM evaluation"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Clear previous results and re-run everything"
    ),
    max_questions: Optional[int] = typer.Option(
        None, "--max-questions", "-n", help="Limit to first N questions"
    ),
):
    """Run the BixBench-50 benchmark suite."""
    import shutil as _shutil
    from bench.runner import BenchRunner

    if force:
        out = Path(output)
        for sub in ("results", "evals", ".preview_cache"):
            d = out / sub
            if d.exists():
                _shutil.rmtree(d)
        for f in ("all_results.json", "llm_eval.json"):
            p = out / f
            if p.exists():
                p.unlink()
        console.print(f"  [dim]Cleared {out}[/dim]")

    if dry_run:
        import json as _json

        with open(manifest) as f:
            questions = _json.load(f)
        if question:
            questions = [q for q in questions if q["question_id"] == question]
        if max_questions:
            questions = questions[:max_questions]

        table = Table(title=f"BixBench Dry Run — {len(questions)} questions")
        table.add_column("#", width=4)
        table.add_column("Question ID", style="cyan", width=14)
        table.add_column("Data", width=5)
        table.add_column("Question", max_width=60)
        table.add_column("Ideal", max_width=30)

        for i, q in enumerate(questions, 1):
            has_data = "Y" if q.get("data_dir") and Path(q["data_dir"]).exists() else "N"
            table.add_row(
                str(i),
                q["question_id"],
                has_data,
                q["question"][:60],
                q["ideal"][:30],
            )
        console.print(table)
        return

    runner = BenchRunner(
        manifest_path=manifest,
        output_dir=output,
        parallel=parallel,
        timeout=timeout,
        max_turns=max_turns,
        model=model,
        eval_model=eval_model,
        no_eval=no_eval,
        only_failed=only_failed,
        question_id=question,
        max_questions=max_questions,
    )

    summary = runner.run()
    if summary.get("total"):
        console.print(
            f"\n[bold]Score: {summary['passed']}/{summary['total']} "
            f"({summary['accuracy']:.1%})[/bold]"
        )


def print_banner(cfg=None):
    """Print the startup banner with molecule illustration."""
    from agent.config import Config
    from rich.padding import Padding
    from rich.table import Table
    from rich.text import Text

    cfg = cfg or Config.load()
    n_tools = _get_loaded_tool_count_hint()
    n_skills = _count_installed_claude_skills()
    model_raw = str(cfg.get("llm.model") or "").strip()
    model_names = {
        "claude-sonnet-4-5-20250929": "Sonnet 4.5",
        "claude-haiku-4-5-20251001": "Haiku 4.5",
        "claude-opus-4-6": "Opus 4.6",
        "gpt-4o": "GPT-4o",
        "gpt-4o-mini": "GPT-4o Mini",
    }
    model_name = model_names.get(model_raw, model_raw)

    tier = _resolve_fastfold_subscription_tier_local(cfg)
    tier_display = _format_plan_label(tier)
    status_parts: list[str] = []
    if model_name:
        status_parts.append(model_name)
    if tier_display:
        status_parts.append(tier_display)
    status_line = " · ".join(status_parts)
    upgrade_version = _get_cached_upgrade_available_version(__version__)

    logo_text = Text.from_markup(BANNER.strip("\n"))
    meta_lines = [
        f"[bold white]Fastfold Agent CLI[/] [dim]v{__version__}[/]",
    ]
    if status_line:
        meta_lines.append(f"[dim]{status_line}[/dim]")
    if upgrade_version:
        meta_lines.append(
            f"[bold yellow]Upgrade available:[/] [dim]v{__version__} -> v{upgrade_version}[/dim] "
            "[dim]Run [/dim][bold #D4148E]/upgrade[/]"
        )
    skills_update = _get_cached_skills_update_safe()
    if skills_update:
        meta_lines.append(
            f"[bold yellow]Skills update available:[/] "
            f"[dim]{skills_update['installed']} -> {skills_update['latest']}[/dim] "
            "[dim]Run [/dim][bold #D4148E]/skills-upgrade[/]"
        )
    meta_lines.append(f"[dim]{n_tools} tools · {n_skills} skills[/dim]")
    meta_lines.append(_random_command_tip_markup())
    meta_lines.append(_random_news_item_markup())
    meta_text = Text.from_markup("\n".join(meta_lines))

    header = Table.grid(padding=(0, 2))
    header.add_column(no_wrap=True)
    header.add_column()
    header.add_row(logo_text, Padding(meta_text, (2, 0, 0, 1)))
    console.print(header)


def run_interactive(
    context: dict,
    output: Optional[Path],
    model: Optional[str],
    verbose: bool,
    resume_id: str = None,
):
    """Run interactive session."""
    from agent.config import Config

    def _pin_startup_to_bottom() -> None:
        """Place startup banner/prompt near terminal bottom like Claude Code."""
        try:
            rows = int(getattr(console.size, "height", 0) or 0)
        except Exception:
            rows = 0
        # Approximate visible startup footprint:
        # banner (~11 lines) + spacing + first prompt/separator.
        startup_lines = 15
        spacer = max(0, rows - startup_lines)
        console.clear()
        if spacer:
            console.print("\n" * spacer, end="")

    cfg = Config.load()
    if model:
        cfg.set("llm.model", model)

    llm_issue = cfg.llm_preflight_issue()
    if llm_issue:
        console.print("\n  [yellow]First-time setup required.[/yellow]\n")
        setup_cmd(api_key=None, openai_api_key=None, fastfold_api_key=None, provider=None)
        # Reload config after setup
        cfg = Config.load()
        llm_issue = cfg.llm_preflight_issue()
        if llm_issue:
            console.print(f"\n  [red]Setup incomplete:[/red] {llm_issue}")
            return

    _pin_startup_to_bottom()
    print_banner(cfg)
    _maybe_offer_fastfold_skills_install_after_upgrade(
        ui=console,
        install_missing=False,
        prompt_if_missing=True,
    )
    # Refresh the skills-update cache in the background so the next boot's banner
    # notice is fresh — no network on this boot's path.
    _start_skills_update_check()
    _start_upgrade_check_refresh()

    console.print()

    terminal = InteractiveTerminal(config=cfg, verbose=verbose)
    terminal.run(initial_context=context, resume_id=resume_id)


def entry():
    """Package entry point."""
    # Dev ergonomics: when invoked from the repo root (or a subdir), prefer the
    # live source file so `uv run fastfold ...` reflects local edits immediately.
    current_cli_path = Path(__file__).resolve()
    candidate_roots = [Path.cwd(), *Path.cwd().parents]
    for root in candidate_roots:
        local_cli = root / "src" / "cli.py"
        if not local_cli.exists():
            continue
        resolved_local = local_cli.resolve()
        if resolved_local == current_cli_path:
            break
        os.execv(sys.executable, [sys.executable, str(resolved_local), *sys.argv[1:]])

    argv = list(sys.argv[1:])
    subcommands = {
        "config",
        "data",
        "tool",
        "skills",
        "skill",
        "add",
        "trace",
        "knowledge",
        "keys",
        "mcp",
        "serve",
        "sync",
        "doctor",
        "setup",
        "release-check",
        "upgrade",
        "report",
        "case-study",
        "bench",
        "agent",
        "run",  # legacy explicit runner command
        "--help",
        "-h",
        "--install-completion",
        "--show-completion",
    }

    # Support `fastfold help` and `fastfold help <subcommand>` as aliases.
    if argv and argv[0] == "help":
        argv = ["--help"] if len(argv) == 1 else [*argv[1:], "--help"]

    # Route plain invocations to hidden `run` command so:
    #   fastfold                       -> interactive mode
    #   fastfold "question"            -> single-query mode
    #   fastfold --smiles ... "q"      -> single-query with context
    # while preserving explicit subcommands like `fastfold config ...`.
    # Backward-compat: allow old `fastfold run <subcommand> ...` invocations by
    # unwrapping the legacy `run` prefix when the remainder is a real subcommand.
    if len(argv) >= 2 and argv[0] == "run" and argv[1] in subcommands:
        argv = argv[1:]

    if not argv or argv[0] not in subcommands:
        argv = ["run", *argv]

    app(args=argv, prog_name="fastfold")


if __name__ == "__main__":
    entry()
