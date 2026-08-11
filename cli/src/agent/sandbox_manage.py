"""CLI helpers for sandbox backend selection (builtin vs Modal)."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from agent.config import Config

# CLI-only preference (mirrors agent.cli_specialist). Keeps interactive /
# `sandwalk sandbox` independent from the web dashboard's sandbox.backend.
CLI_SANDBOX_CONFIG_KEY = "agent.cli_sandbox"
_ALIASES = {
    "off": "builtin",
    "local": "builtin",
    "local sandbox": "builtin",
    "built-in": "builtin",
    "builtin": "builtin",
    "on": "modal",
    "modal": "modal",
    "modal sandbox": "modal",
    "remote": "modal",
}


def normalize_sandbox_backend(raw: Any) -> str:
    value = str(raw or "builtin").strip().lower()
    value = _ALIASES.get(value, value)
    if value not in {"builtin", "modal"}:
        raise ValueError("sandbox backend must be 'builtin' or 'modal'")
    return value


def get_sandbox_backend(config: Config | None = None) -> str:
    """Return the CLI sandbox backend. Default is Local Sandbox unless Modal is set."""
    cfg = config or Config.load()
    raw = cfg.get(CLI_SANDBOX_CONFIG_KEY, "")
    if raw is None or str(raw).strip() == "":
        return "builtin"
    try:
        return normalize_sandbox_backend(raw)
    except ValueError:
        return "builtin"


def sandbox_toolbar_label(backend: str | None = None, config: Config | None = None) -> str:
    kind = backend or get_sandbox_backend(config)
    return "Modal Sandbox" if kind == "modal" else "Local Sandbox"


def set_sandbox_backend(backend: str, config: Config | None = None) -> str:
    cfg = config or Config.load()
    normalized = normalize_sandbox_backend(backend)
    if normalized == "modal":
        from agent.sandbox_probe import modal_tokens_present

        ok, detail = modal_tokens_present(cfg)
        if not ok:
            raise RuntimeError(
                detail
                or "Modal tokens missing. Set compute.modal_token_id / "
                "compute.modal_token_secret (Integrations → Modal)."
            )
    cfg.set(CLI_SANDBOX_CONFIG_KEY, normalized)
    cfg.save()
    return normalized


def toggle_sandbox_backend(config: Config | None = None) -> str:
    cfg = config or Config.load()
    current = get_sandbox_backend(cfg)
    target = "builtin" if current == "modal" else "modal"
    return set_sandbox_backend(target, cfg)


def _format_bytes(n: int | None) -> str:
    if n is None or n <= 0:
        return "—"
    gb = n / (1024**3)
    if gb >= 10:
        return f"{gb:.0f} GB"
    if gb >= 1:
        return f"{gb:.1f} GB"
    mb = n / (1024**2)
    return f"{mb:.0f} MB"


def _print_local_host_info(console: Console) -> None:
    try:
        from agent_server.status_service import get_status_report

        report = get_status_report(version="cli")
        system = report.system
    except Exception:  # noqa: BLE001
        return
    chip = str(getattr(system, "chip_name", None) or getattr(system, "label", "") or "").strip()
    if chip:
        console.print(f"  Host: [cyan]{chip}[/cyan]")
    ram_used = getattr(system, "ram_used_bytes", None)
    ram_total = getattr(system, "ram_total_bytes", None)
    if isinstance(ram_total, int) and ram_total > 0:
        console.print(
            f"  RAM:  {_format_bytes(int(ram_used) if isinstance(ram_used, int) else None)}"
            f" / {_format_bytes(ram_total)}"
        )
    gpu_cores = getattr(system, "gpu_cores", None)
    if isinstance(gpu_cores, int) and gpu_cores > 0:
        console.print(f"  GPU:  {gpu_cores} cores (host)")


def _print_modal_compute_info(console: Console, cfg: Config) -> None:
    from agent.sandbox_backend.profile import (
        DEFAULT_CPU_IMAGE,
        DEFAULT_GPU_IMAGE,
        sandbox_compute_type,
        sandbox_gpu_class,
        sandbox_image_ref,
    )

    compute_type = sandbox_compute_type(cfg)
    cpu_cores = float(cfg.get("sandbox.cpu_cores") or 2.0)
    ram_gb = float(cfg.get("sandbox.ram_gb") or 8.0)
    base_image = sandbox_image_ref(cfg, compute_type=compute_type)
    console.print(f"  Mode: [cyan]{compute_type.upper()}[/cyan]")
    if compute_type == "gpu":
        console.print(f"  GPU:  [cyan]{sandbox_gpu_class(cfg)}[/cyan]")
    console.print(f"  CPU:  {cpu_cores:g} cores")
    console.print(f"  RAM:  {ram_gb:g} GB")
    console.print(f"  Base image: [cyan]{base_image}[/cyan]")
    cpu_image = str(cfg.get("sandbox.cpu_image") or DEFAULT_CPU_IMAGE)
    gpu_image = str(cfg.get("sandbox.gpu_image") or DEFAULT_GPU_IMAGE)
    if compute_type == "gpu" and cpu_image != gpu_image:
        console.print(f"  [dim]CPU image:[/dim]  {cpu_image}")
    if compute_type == "cpu":
        console.print(f"  [dim]GPU image:[/dim]  {gpu_image}")


def _print_gpu_setup_hints(console: Console) -> None:
    console.print("  [dim]GPU Modal setup (CUDA comes from the GPU base image):[/dim]")
    console.print("    sandwalk config set sandbox.compute_type gpu")
    console.print("    sandwalk config set sandbox.gpu_class T4")
    console.print(
        "    sandwalk config set sandbox.gpu_image "
        "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime"
    )
    console.print("    /sandbox modal   # then restart / ask the agent to sandbox_start")


def handle_sandbox_argv(argv: list[str], console: Console, config: Config | None = None) -> None:
    """Interactive `/sandbox` and `sandwalk sandbox` command handler."""
    cfg = config or Config.load()
    parts = [str(p).strip() for p in argv if str(p).strip()]
    if parts and parts[0].lstrip("/").lower() == "sandbox":
        parts = parts[1:]

    action = (parts[0].lower() if parts else "status")
    rest = parts[1:] if len(parts) > 1 else []

    if action in {"help", "-h", "--help"}:
        console.print("  [bold]/sandbox[/bold] — choose Local Sandbox or Modal Sandbox")
        console.print("    /sandbox              Interactive picker (Local + Modal presets)")
        console.print("    /sandbox status       Show backend + compute/image")
        console.print("    /sandbox builtin|off  Use Local Sandbox (default)")
        console.print("    /sandbox modal|on     Use Modal Sandbox")
        console.print("    /sandbox toggle       Flip Local ↔ Modal")
        console.print("")
        _print_gpu_setup_hints(console)
        return

    if action in {"status", "show", "get"}:
        kind = get_sandbox_backend(cfg)
        label = sandbox_toolbar_label(kind)
        console.print(f"  Sandbox: [bold]{label}[/bold] ([cyan]{kind}[/cyan])")
        if kind == "builtin":
            console.print("  [dim]Default for CLI — runs on this machine.[/dim]")
            _print_local_host_info(console)
        if kind == "modal":
            from agent.sandbox_probe import modal_tokens_present

            ok, detail = modal_tokens_present(cfg)
            if ok:
                console.print("  [dim]Modal tokens configured.[/dim]")
            else:
                console.print(f"  [yellow]Modal tokens missing:[/yellow] {detail}")
            _print_modal_compute_info(console, cfg)
            from agent.sandbox_backend.profile import sandbox_compute_type

            if sandbox_compute_type(cfg) != "gpu":
                console.print(
                    "  [yellow]Compute is CPU[/yellow] — GPU class in settings is unused "
                    "until sandbox.compute_type=gpu."
                )
                _print_gpu_setup_hints(console)
        console.print("  [dim]Change with[/dim] /sandbox  (picker)  or  /sandbox builtin|modal|toggle")
        return

    if action == "toggle":
        try:
            kind = toggle_sandbox_backend(cfg)
        except RuntimeError as exc:
            console.print(f"  [red]{exc}[/red]")
            return
        console.print(
            f"  Sandbox → [bold]{sandbox_toolbar_label(kind)}[/bold] ([cyan]{kind}[/cyan])"
        )
        return

    if action in _ALIASES or action in {"builtin", "modal"}:
        try:
            kind = set_sandbox_backend(action, cfg)
        except (RuntimeError, ValueError) as exc:
            console.print(f"  [red]{exc}[/red]")
            return
        console.print(
            f"  Sandbox → [bold]{sandbox_toolbar_label(kind)}[/bold] ([cyan]{kind}[/cyan])"
        )
        if kind == "modal":
            _print_modal_compute_info(console, cfg)
        return

    if rest:
        console.print(f"  [yellow]Unknown sandbox args:[/yellow] {' '.join(parts)}")
    else:
        console.print(f"  [yellow]Unknown sandbox command:[/yellow] {action}")
    console.print("  [dim]Try[/dim] /sandbox help")
