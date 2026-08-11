"""`sandwalk knowledge` — substrate status, ingestion, and search."""

import typer
from rich.table import Table

from cli.app import app, console

knowledge_app = typer.Typer(help="Manage knowledge substrate, ingestion, and quality gates")
app.add_typer(knowledge_app, name="knowledge")


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
    query: str | None = typer.Option(None, "--query", "-q", help="Query for API sources"),
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
    predicate: str | None = typer.Option(None, "--predicate", help="Filter predicate"),
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
