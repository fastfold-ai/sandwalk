"""`sandwalk bench` — run the BixBench-50 benchmark suite."""

from pathlib import Path

import typer
from rich.table import Table

from cli.app import app, console


@app.command("bench")
def bench(
    question: str | None = typer.Option(
        None, "--question", "-q", help="Run a single question by ID"
    ),
    parallel: int = typer.Option(10, "--parallel", "-p", help="Number of parallel workers"),
    timeout: int = typer.Option(300, "--timeout", help="Timeout per question in seconds"),
    max_turns: int = typer.Option(15, "--max-turns", help="Max agentic loop turns"),
    model: str | None = typer.Option(None, "--model", "-m", help="LLM model override"),
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
    max_questions: int | None = typer.Option(
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
