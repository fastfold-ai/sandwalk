"""CLI: ``sandwalk-bench``."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from sandwalk_bench import __version__
from sandwalk_bench.bixbench import download_jsonl, load_jsonl, summarize
from sandwalk_bench.pack import expand_matrix, list_packs, load_pack
from sandwalk_bench.paths import PACKS_DIR
from sandwalk_bench.spawn import spawn_matrix
from sandwalk_bench.verify import extract_final_answer, grade

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()
bix_app = typer.Typer(no_args_is_help=True, help="BixBench-Verified-50 helpers")
app.add_typer(bix_app, name="bixbench")


@app.callback()
def main() -> None:
    """Sandwalk agent benchmarking suite."""


@app.command("version")
def version() -> None:
    console.print(__version__)


@app.command("packs")
def packs_cmd() -> None:
    """List YAML packs under packs/."""
    table = Table(title="sandwalk-bench packs")
    table.add_column("file")
    table.add_column("pack id")
    table.add_column("version")
    table.add_column("questions", justify="right")
    table.add_column("matrices")
    for path in list_packs():
        pack = load_pack(path)
        table.add_row(
            path.name,
            pack.id,
            pack.version,
            str(len(pack.questions)),
            ", ".join(pack.matrices.keys()) or "—",
        )
    console.print(table)


@app.command("show")
def show_cmd(
    pack: str = typer.Argument(..., help="Pack path or filename in packs/"),
    question: str | None = typer.Option(None, "--question", "-q"),
) -> None:
    """Show pack questions (or one question)."""
    p = load_pack(pack)
    rows = p.questions if not question else [p.get(question)]
    table = Table(title=f"{p.id} v{p.version}")
    table.add_column("id", style="cyan")
    table.add_column("eval")
    table.add_column("title")
    table.add_column("skills")
    table.add_column("mcps")
    for q in rows:
        table.add_row(
            q.id,
            str(q.eval_mode),
            q.title[:40],
            ",".join(q.skills)[:32],
            ",".join(q.mcps)[:32],
        )
    console.print(table)


@app.command("matrix")
def matrix_cmd(
    pack: str = typer.Argument(...),
    name: str = typer.Argument(..., help="Matrix name inside the pack"),
) -> None:
    """Expand a matrix to cells (dry preview)."""
    p = load_pack(pack)
    cells = expand_matrix(p, name)
    table = Table(title=f"{p.id} / {name}")
    table.add_column("#", justify="right")
    table.add_column("question")
    table.add_column("model")
    table.add_column("title")
    for i, c in enumerate(cells, 1):
        table.add_row(str(i), c.question_id, f"{c.provider}:{c.model_id}", c.title)
    console.print(table)


@app.command("spawn")
def spawn_cmd(
    pack: str = typer.Argument(...),
    matrix: str = typer.Argument(...),
    base_url: str = typer.Option("http://127.0.0.1:8787", "--base-url"),
    api_key: str | None = typer.Option(None, "--api-key", envvar="SANDWALK_API_KEY"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    out: Path | None = typer.Option(None, "--out", help="Write run manifest JSON"),
    project_name: str | None = typer.Option(
        None,
        "--project-name",
        help="Project name (default: bench · <pack> · <matrix> · <utc timestamp>)",
    ),
    project_description: str | None = typer.Option(
        None,
        "--project-description",
        help="Override auto description (pack/matrix/models/question ids)",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Reuse an existing project instead of creating one",
    ),
    no_project: bool = typer.Option(
        False,
        "--no-project",
        help="Do not create/attach a Project (legacy flat sidebar)",
    ),
) -> None:
    """Spawn agent-server chat sessions for a matrix (under one Project by default)."""
    key = api_key
    if not key and not dry_run:
        try:
            key = subprocess.check_output(
                ["sandwalk", "auth", "show"], text=True
            ).strip()
        except Exception as exc:  # noqa: BLE001
            raise typer.BadParameter(
                "Pass --api-key or set SANDWALK_API_KEY (or have sandwalk auth show)."
            ) from exc
    results = spawn_matrix(
        pack_path=pack,
        matrix_name=matrix,
        base_url=base_url,
        api_key=key or "",
        dry_run=dry_run,
        project_name=project_name,
        project_description=project_description,
        project_id=project_id,
        no_project=no_project,
    )
    console.print_json(data=results)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        console.print(f"wrote {out}")
    proj = results.get("project") if isinstance(results, dict) else None
    if proj and proj.get("name"):
        console.print(
            f"[bold]Project:[/bold] {proj.get('name')}  "
            f"[dim]id={proj.get('id')}[/dim]"
        )


@app.command("grade")
def grade_cmd(
    eval_mode: str = typer.Option(...),
    ideal: str = typer.Option(...),
    prediction_file: Path = typer.Option(..., "--prediction-file", "-f"),
) -> None:
    """Grade a prediction file against ideal (str/range for now)."""
    text = prediction_file.read_text(encoding="utf-8")
    pred = extract_final_answer(text)
    g = grade(eval_mode, ideal, pred)
    console.print_json(data=g.__dict__)
    raise typer.Exit(0 if g.ok else 1)


@bix_app.command("download")
def bix_download(
    force: bool = typer.Option(False, "--force"),
    token: str | None = typer.Option(None, "--token", envvar="HF_TOKEN"),
) -> None:
    """Download BixBench-Verified-50.jsonl into .cache/ (needs HF_TOKEN)."""
    path = download_jsonl(token=token, force=force)
    console.print(f"cached {path}")


@bix_app.command("info")
def bix_info() -> None:
    """Summarize cached Verified-50 schema/stats."""
    console.print_json(data=summarize())


@bix_app.command("list")
def bix_list(limit: int = typer.Option(20, "--limit", "-n")) -> None:
    """List cached upstream questions."""
    rows = load_jsonl()
    table = Table(title="BixBench-Verified-50")
    table.add_column("question_id", style="cyan")
    table.add_column("eval")
    table.add_column("question", max_width=70)
    for r in rows[:limit]:
        table.add_row(
            str(r.get("question_id") or r.get("short_id")),
            str(r.get("eval_mode")),
            str(r.get("question") or "")[:70],
        )
    console.print(table)
    if len(rows) > limit:
        console.print(f"… {len(rows) - limit} more")


if __name__ == "__main__":
    app()
