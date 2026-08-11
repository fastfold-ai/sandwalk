"""`sandwalk eval` — headless Dashboard Bench (no UI).

Talks to a running agent-server when available (`sandwalk serve` / the app),
otherwise runs in-process against the same sessions store and writes results
to ``~/.sandwalk/bench-runs/`` so the Dashboard Results tab can show them.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
import typer
from rich.table import Table

from cli.app import app, console

eval_app = typer.Typer(help="Run Dashboard Bench suites headlessly (no UI)")
app.add_typer(eval_app, name="eval")


def _fail(msg: str, *, code: int = 1) -> None:
    console.print(f"[red]{msg}[/red]")
    raise typer.Exit(code=code)


def _base_url(explicit: str | None) -> str:
    raw = (
        explicit
        or os.environ.get("SANDWALK_SERVER_URL")
        or os.environ.get("FASTFOLD_SERVER_URL")
        or os.environ.get("FASTFOLD_AGENT_URL")
        or "http://127.0.0.1:8787"
    )
    return raw.rstrip("/")


def _api_key() -> str | None:
    env = (
        os.environ.get("SANDWALK_SERVER_API_KEY")
        or os.environ.get("FASTFOLD_SERVER_API_KEY")
        or ""
    ).strip()
    if env:
        return env
    try:
        from agent_server.auth_settings import load_settings

        return (load_settings().api_key or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


def _headers() -> dict[str, str]:
    key = _api_key()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def _server_reachable(base: str) -> bool:
    try:
        with httpx.Client(timeout=2.0) as client:
            r = client.get(f"{base}/v1/health", headers=_headers())
            return r.status_code < 500
    except Exception:  # noqa: BLE001
        return False


def _http_json(
    method: str,
    base: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> Any:
    with httpx.Client(timeout=timeout) as client:
        r = client.request(
            method,
            f"{base}{path}",
            headers={**_headers(), "Content-Type": "application/json"},
            json=json_body,
        )
        if r.status_code >= 400:
            detail = r.text
            try:
                detail = r.json().get("detail") or detail
            except Exception:  # noqa: BLE001
                pass
            _fail(f"HTTP {r.status_code}: {detail}")
        if not r.content:
            return None
        return r.json()


@eval_app.command("suites")
def eval_suites(
    base_url: str | None = typer.Option(
        None, "--base-url", help="Agent-server URL (default localhost:8787)"
    ),
):
    """List available Dashboard Bench suites."""
    base = _base_url(base_url)
    if _server_reachable(base):
        data = _http_json("GET", base, "/v1/bench/packs")
        cards = data.get("data") or []
    else:
        from agent_server.bench_service.catalog import list_suite_cards

        cards = [c.model_dump(by_alias=True) for c in list_suite_cards()]

    table = Table(title="Bench suites", show_lines=False)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title")
    table.add_column("Questions", justify="right")
    table.add_column("Default", justify="right")
    table.add_column("OK")
    for card in cards:
        ok = card.get("available", True)
        table.add_row(
            str(card.get("id") or ""),
            str(card.get("title") or ""),
            str(card.get("questionCount") or card.get("question_count") or 0),
            str(
                card.get("defaultSampleSize")
                or card.get("default_sample_size")
                or "—"
            ),
            "yes" if ok else "no",
        )
    console.print(table)


@eval_app.command("status")
def eval_status(
    base_url: str | None = typer.Option(None, "--base-url"),
):
    """Show active / queued Dashboard Bench runs (needs agent-server)."""
    base = _base_url(base_url)
    if not _server_reachable(base):
        console.print(
            "[yellow]No agent-server at[/yellow] "
            f"{base}. Start with `sandwalk serve`, or use `sandwalk eval run` "
            "(in-process)."
        )
        raise typer.Exit(code=1)
    status = _http_json("GET", base, "/v1/bench/runs/active")
    console.print_json(data=status)


@eval_app.command("results")
def eval_results(
    base_url: str | None = typer.Option(None, "--base-url"),
    limit: int = typer.Option(20, "--limit", "-n", min=1),
):
    """List scored results (from server if up, else local bench-runs/)."""
    base = _base_url(base_url)
    if _server_reachable(base):
        data = _http_json("GET", base, "/v1/bench/runs")
        rows = data.get("data") or []
    else:
        from agent_server.bench_service.results_store import list_results

        rows = list_results()

    if not rows:
        console.print("[dim]No results yet.[/dim]")
        raise typer.Exit()

    table = Table(title=f"Bench results (latest {min(limit, len(rows))})")
    table.add_column("Run", style="dim", no_wrap=True, max_width=12)
    table.add_column("Suite")
    table.add_column("Model")
    table.add_column("Score", justify="right")
    table.add_column("n", justify="right")
    table.add_column("s", justify="right")
    for row in rows[:limit]:
        acc = float(row.get("accuracy") or 0)
        rid = str(row.get("runId") or row.get("run_id") or "")
        table.add_row(
            rid[:8],
            str(row.get("benchmark") or ""),
            str(row.get("modelId") or row.get("model_id") or ""),
            f"{acc * 100:.1f}%",
            f"{row.get('correct') or 0}/{row.get('total') or 0}",
            str(row.get("timeS") or row.get("time_s") or ""),
        )
    console.print(table)


@eval_app.command("show")
def eval_show(
    run_id: str = typer.Argument(..., help="Run id (prefix ok)"),
    base_url: str | None = typer.Option(None, "--base-url"),
):
    """Print one result JSON."""
    base = _base_url(base_url)
    if _server_reachable(base):
        rows = (_http_json("GET", base, "/v1/bench/runs").get("data") or [])
        match = next(
            (
                r
                for r in rows
                if str(r.get("runId") or "").startswith(run_id)
                or str(r.get("runId") or "") == run_id
            ),
            None,
        )
        if not match:
            _fail(f"No run matching {run_id!r}")
        full = _http_json("GET", base, f"/v1/bench/runs/{match['runId']}")
        console.print_json(data=full)
        return

    from agent_server.bench_service.results_store import get_result, list_results

    match_id = None
    for row in list_results():
        rid = str(row.get("run_id") or "")
        if rid == run_id or rid.startswith(run_id):
            match_id = rid
            break
    if not match_id:
        _fail(f"No run matching {run_id!r}")
    console.print_json(data=get_result(match_id) or {})


def _parse_suite_spec(
    raw: str, *, default_sample: int | None
) -> tuple[str, int | None]:
    """Parse ``suite`` or ``suite:n`` / ``suite=n`` (Dashboard sample size)."""
    text = str(raw or "").strip()
    if not text:
        _fail("Empty --suite value")
    for sep in (":", "="):
        if sep not in text:
            continue
        left, right = text.rsplit(sep, 1)
        suite_id = left.strip()
        size_text = right.strip()
        if suite_id and size_text.isdigit():
            return suite_id, int(size_text)
    return text, default_sample


@eval_app.command("run")
def eval_run(
    suite: list[str] = typer.Option(
        ...,
        "--suite",
        "-s",
        help=(
            "Suite id (repeatable). Use id:n for per-suite sample size "
            "(e.g. mmlu:30, bio-capybara-full:5)."
        ),
    ),
    sample: int | None = typer.Option(
        None,
        "--sample",
        "-n",
        help="Default sample size when a --suite has no :n suffix",
    ),
    model: str | None = typer.Option(
        None, "--model", "-m", help="Model id (default = runtime settings)"
    ),
    models: list[str] = typer.Option(
        None, "--compare", help="Extra models to queue after --model"
    ),
    specialist: str | None = typer.Option(
        None, "--specialist", help="Specialist id (optional)"
    ),
    workers: int = typer.Option(
        1,
        "--workers",
        "-w",
        min=1,
        max=8,
        help="Parallel cells within each suite (Dashboard Workers)",
    ),
    cleanup: bool = typer.Option(
        False,
        "--cleanup/--no-cleanup",
        help="Delete bench project chats after a successful run",
    ),
    effort: str | None = typer.Option(
        None,
        "--effort",
        help="Reasoning effort (low|medium|high|xhigh) — applied to runtime settings",
    ),
    fast: bool | None = typer.Option(
        None,
        "--fast/--no-fast",
        help="Reasoning Fast (thinking off) — applied to runtime settings",
    ),
    base_url: str | None = typer.Option(None, "--base-url"),
    wait: bool = typer.Option(
        True, "--wait/--no-wait", help="Block until the queued job finishes"
    ),
    poll: float = typer.Option(2.0, "--poll", help="Seconds between status polls"),
    local: bool = typer.Option(
        False,
        "--local",
        help="Force in-process run (fails if agent-server already holds the DB)",
    ),
):
    """Queue and run Dashboard Bench suites; results land in bench-runs/."""
    suite_specs = [_parse_suite_spec(s, default_sample=sample) for s in suite]
    # camelCase matches ApiModel wire format used by /v1/bench/spawn.
    payload = {
        "suites": [
            {"suiteId": sid, "sampleSize": n} for sid, n in suite_specs
        ],
        "model": model,
        "models": list(models or []),
        "specialistId": specialist,
        "concurrency": max(1, int(workers or 1)),
        "cleanupSessions": bool(cleanup),
        "clientSurface": "cli",
    }
    local_payload = {
        "suites": [
            {"suite_id": sid, "sample_size": n} for sid, n in suite_specs
        ],
        "model": model,
        "models": list(models or []),
        "specialist_id": specialist,
        "concurrency": max(1, int(workers or 1)),
        "cleanup_sessions": bool(cleanup),
        "client_surface": "cli",
    }

    base = _base_url(base_url)
    use_http = (not local) and _server_reachable(base)

    if use_http:
        console.print(f"[dim]Using agent-server[/dim] {base}")
        if effort is not None or fast is not None:
            patch: dict[str, Any] = {}
            if model:
                patch["model"] = model
            if effort is not None:
                patch["reasoningEffort"] = effort
            if fast is not None:
                patch["reasoningFast"] = bool(fast)
            _http_json("PATCH", base, "/v1/settings/runtime", json_body=patch)
        resp = _http_json("POST", base, "/v1/bench/spawn", json_body=payload)
        run_ids = resp.get("runIds") or resp.get("run_ids") or []
        console.print(
            f"Queued [cyan]{len(run_ids)}[/cyan] job(s): "
            + ", ".join(str(r)[:8] for r in run_ids)
        )
        if not wait:
            return
        _wait_http(base, run_ids, poll=poll)
        _print_finished(base, run_ids)
        return

    console.print(
        "[dim]No reachable agent-server — running in-process "
        "(same DB / bench-runs as Dashboard).[/dim]"
    )
    if effort is not None or fast is not None:
        local_payload["reasoning_effort"] = effort
        local_payload["reasoning_fast"] = fast
    result_rows = _run_local(local_payload)
    for row in result_rows:
        acc = float(row.get("accuracy") or 0)
        console.print(
            f"[green]✓[/green] {row.get('benchmark')} · {row.get('model_id')} · "
            f"{acc * 100:.1f}% ({row.get('correct')}/{row.get('total')}) "
            f"[{str(row.get('run_id') or '')[:8]}]"
        )


def _wait_http(base: str, run_ids: list[str], *, poll: float) -> None:
    wanted = set(run_ids)
    console.print("[dim]Waiting for completion…[/dim]")
    while True:
        status = _http_json("GET", base, "/v1/bench/runs/active")
        running = bool(status.get("running"))
        queue = status.get("queue") or []
        current = status.get("currentRunId") or status.get("current_run_id")
        progress = status.get("lastProgress") or status.get("last_progress") or {}
        msg = progress.get("message") or status.get("phase") or "…"
        console.print(
            f"  {msg}"
            + (f" · current={str(current)[:8]}" if current else "")
            + (f" · queued={len(queue)}" if queue else ""),
            highlight=False,
        )
        if not running and not queue:
            # Ensure our runs are persisted (may finish between polls).
            rows = _http_json("GET", base, "/v1/bench/runs").get("data") or []
            done = {
                str(r.get("runId") or r.get("run_id") or "")
                for r in rows
            }
            if wanted.issubset(done) or not wanted:
                return
            # Jobs may have failed without a result file — stop if idle.
            return
        time.sleep(max(0.5, poll))


def _print_finished(base: str, run_ids: list[str]) -> None:
    rows = _http_json("GET", base, "/v1/bench/runs").get("data") or []
    by_id = {
        str(r.get("runId") or r.get("run_id") or ""): r for r in rows
    }
    printed = False
    for rid in run_ids:
        row = by_id.get(rid)
        if not row:
            # Prefix match (short ids) or older servers that regenerated ids.
            row = next(
                (
                    r
                    for key, r in by_id.items()
                    if key.startswith(rid) or rid.startswith(key[:8])
                ),
                None,
            )
        if not row:
            continue
        printed = True
        acc = float(row.get("accuracy") or 0)
        real = str(row.get("runId") or row.get("run_id") or rid)
        console.print(
            f"[green]✓[/green] {row.get('benchmark')} · "
            f"{row.get('modelId') or row.get('model_id')} · "
            f"{acc * 100:.1f}% ({row.get('correct')}/{row.get('total')}) "
            f"[{real[:8]}]"
        )
    if not printed and rows:
        # Fallback: show the newest result (common when queue id ≠ result id).
        row = rows[0]
        acc = float(row.get("accuracy") or 0)
        rid = str(row.get("runId") or row.get("run_id") or "")
        console.print(
            f"[green]✓[/green] {row.get('benchmark')} · "
            f"{row.get('modelId') or row.get('model_id')} · "
            f"{acc * 100:.1f}% ({row.get('correct')}/{row.get('total')}) "
            f"[{rid[:8]}]"
        )
    elif not printed:
        console.print(
            "[yellow]No result file yet — check `sandwalk eval results`.[/yellow]"
        )


def _run_local(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Boot a minimal agent-server stack in-process and run suites sequentially."""
    import asyncio
    import threading

    from agent_server.app import create_app
    from agent_server.bench_service.queue_runner import _split_suite
    from agent_server.bench_service.spawn_core import run_agent_suite
    from agent_server.models.bench import BenchSpawnRequest, BenchSuiteRef
    from agent_server.sandbox_events import sandbox_event_bus
    from agent_server.settings_service import SettingsService

    req = BenchSpawnRequest(
        suites=[
            BenchSuiteRef(suite_id=s["suite_id"], sample_size=s.get("sample_size"))
            for s in payload["suites"]
        ],
        model=payload.get("model"),
        models=list(payload.get("models") or []),
        specialist_id=payload.get("specialist_id"),
        thinking=bool(payload.get("thinking")),
        provider=payload.get("provider"),
        project_name=payload.get("project_name"),
        concurrency=max(1, int(payload.get("concurrency") or 1)),
        cleanup_sessions=bool(payload.get("cleanup_sessions")),
        client_surface=payload.get("client_surface") or "cli",
    )

    try:
        fastapi_app = create_app()
    except Exception as exc:  # noqa: BLE001
        console.print(
            "[red]Could not open the local agent DB.[/red] "
            "If the Sandwalk app / `sandwalk serve` is already running, omit "
            "`--local` so this command uses HTTP instead.\n"
            f"[dim]{exc}[/dim]"
        )
        raise typer.Exit(code=1) from exc

    deps = fastapi_app.state.deps
    settings = SettingsService.get()
    effort = payload.get("reasoning_effort")
    fast = payload.get("reasoning_fast")
    if effort is not None or fast is not None:
        from agent_server.models.settings import UpdateRuntimeSettingsRequest

        SettingsService.update(
            UpdateRuntimeSettingsRequest(
                model=req.model,
                reasoning_effort=None if effort is None else str(effort),
                reasoning_fast=None if fast is None else bool(fast),
            )
        )
        settings = SettingsService.get()
    models = list(req.models or [])
    if req.model:
        models.insert(0, req.model)
    if not models:
        models = [settings.model]

    loop = asyncio.new_event_loop()

    def _loop_thread() -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    thread = threading.Thread(target=_loop_thread, name="sandwalk-eval-loop", daemon=True)
    thread.start()
    sandbox_event_bus.bind_loop(loop)

    finished: list[dict[str, Any]] = []
    try:
        for model_id in models:
            for suite in req.suites:
                pack_id, matrix = _split_suite(suite.suite_id)
                console.print(
                    f"[cyan]→[/cyan] {suite.suite_id} · {model_id}"
                    + (
                        f" · n={suite.sample_size}"
                        if suite.sample_size
                        else ""
                    )
                )

                def _progress(p: dict[str, Any]) -> None:
                    msg = p.get("message") or p.get("phase") or ""
                    cur = p.get("bench_current") or p.get("current") or 0
                    tot = p.get("bench_total") or p.get("total") or 0
                    if msg:
                        console.print(
                            f"  {msg} · {cur}/{tot}",
                            highlight=False,
                        )

                row = run_agent_suite(
                    deps=deps,
                    suite_id=suite.suite_id,
                    pack_id=pack_id,
                    matrix=matrix,
                    model_id=model_id,
                    provider=req.provider or settings.provider,
                    sample_size=suite.sample_size,
                    project_name=req.project_name,
                    specialist_id=req.specialist_id,
                    thinking=bool(req.thinking),
                    client_surface=req.client_surface or "cli",
                    concurrency=req.concurrency,
                    cleanup_sessions=bool(req.cleanup_sessions),
                    on_progress=_progress,
                )
                finished.append(row)
                # Persist is inside run_agent_suite via save_result.
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        try:
            deps.store.close()
        except Exception:  # noqa: BLE001
            pass

    return finished
