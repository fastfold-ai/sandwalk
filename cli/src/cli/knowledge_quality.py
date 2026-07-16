"""`sandwalk knowledge` — ranking, contradictions, schema, and benchmark gates."""

import typer
from rich.table import Table

from cli.app import console
from cli.knowledge import knowledge_app


@knowledge_app.command("rank")
def knowledge_rank(
    entity_id: str | None = typer.Option(None, "--entity-id", help="Entity id filter"),
    predicate: str | None = typer.Option(None, "--predicate", help="Predicate filter"),
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
    entity_id: str | None = typer.Option(None, "--entity-id", help="Entity id filter"),
    predicate: str | None = typer.Option(None, "--predicate", help="Predicate filter"),
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
    monitor: str | None = typer.Option(None, "--monitor", help="Single monitor to update"),
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
