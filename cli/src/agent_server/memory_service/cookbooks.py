"""Runnable Cookbook Modes (Ontologies, Stored Queries, and Starter Seeds)."""

from __future__ import annotations

from typing import Any

from agent_server.models.memory import (
    CookbookSummary,
    OntologyEdgeTypeDef,
    OntologyLayerDef,
    OntologyNodeTypeDef,
    OntologyPropertyDef,
    StoredQueryDef,
)


def _prop(
    name: str,
    prop_type: str = "String",
    *,
    is_key: bool = False,
    is_indexed: bool = False,
    optional: bool = False,
) -> OntologyPropertyDef:
    return OntologyPropertyDef(
        name=name,
        type=prop_type,
        is_key=is_key,
        is_indexed=is_indexed,
        optional=optional,
    )


def _render_pg_schema(
    title: str,
    node_types: list[OntologyNodeTypeDef],
    edge_types: list[OntologyEdgeTypeDef],
) -> str:
    lines: list[str] = [f"// {title} — Sandwalk Omnigraph Schema (.pg)", ""]
    for nt in node_types:
        if nt.description:
            lines.append(f"// {nt.description}")
        lines.append(f"node {nt.name} {{")
        for p in nt.properties:
            opt = "?" if p.optional else ""
            ann = " @key" if p.is_key else (" @index" if p.is_indexed else "")
            lines.append(f"    {p.name}: {p.type}{opt}{ann}")
        lines.append("}")
        lines.append("")
    for et in edge_types:
        lines.append(f"edge {et.predicate}: {et.source_type} -> {et.target_type}")
    return "\n".join(lines).strip() + "\n"


COOKBOOK_DEFINITIONS: dict[str, dict[str, Any]] = {
    "industry-intel": {
        "id": "industry-intel",
        "number": "01",
        "name": "Industry intel",
        "tagline": "Track AI and ML market signals through the SPIKE frame: signals, patterns, insights, and know-how.",
        "description": (
            "Models external market signals, recurring patterns, analytical insights, "
            "and operational know-how using the SPIKE intelligence framework."
        ),
        "default_for": "Market & technology intelligence",
        "layers": [
            OntologyLayerDef(
                id="sources",
                label="Layer 1 · Sources & Elements",
                description="Observed artifacts, companies, models, and concrete subjects.",
                node_types=["Element", "SourceArtifact"],
            ),
            OntologyLayerDef(
                id="spike",
                label="Layer 2 · SPIKE Signals & Patterns",
                description="Dated market signals and the recurring patterns they form or contradict.",
                node_types=["Signal", "Pattern"],
            ),
            OntologyLayerDef(
                id="synthesis",
                label="Layer 3 · Insights & Know-How",
                description="Actionable interpretations and reusable operational playbooks.",
                node_types=["Insight", "KnowHow"],
            ),
        ],
        "node_types": [
            OntologyNodeTypeDef(
                name="Element",
                layer="sources",
                color="blue",
                description="Concrete company, model, product, or technology.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                    _prop("kind", is_indexed=True),
                    _prop("summary", optional=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="SourceArtifact",
                layer="sources",
                color="teal",
                description="Dated report, benchmark, release note, or primary source.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("title", is_indexed=True),
                    _prop("url", optional=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Signal",
                layer="spike",
                color="amber",
                description="Observed fact or event anchored to a source.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("headline", is_indexed=True),
                    _prop("observed_at", optional=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Pattern",
                layer="spike",
                color="violet",
                description="Recurring dynamic or challenge formed by multiple signals.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                    _prop("status", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Insight",
                layer="synthesis",
                color="green",
                description="Strategic interpretation derived from patterns.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("title", is_indexed=True),
                    _prop("implication", optional=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="KnowHow",
                layer="synthesis",
                color="pink",
                description="Tactical practice or recipe validated by insights.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                    _prop("playbook", optional=True),
                ],
            ),
        ],
        "edge_types": [
            OntologyEdgeTypeDef(
                predicate="FormsPattern",
                source_type="Signal",
                target_type="Pattern",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="ContradictsPattern",
                source_type="Signal",
                target_type="Pattern",
                polarity="contradict",
            ),
            OntologyEdgeTypeDef(
                predicate="HighlightsPattern",
                source_type="Insight",
                target_type="Pattern",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="AboutElement",
                source_type="Signal",
                target_type="Element",
                polarity="neutral",
            ),
            OntologyEdgeTypeDef(
                predicate="SpottedIn",
                source_type="Signal",
                target_type="SourceArtifact",
                polarity="neutral",
            ),
            OntologyEdgeTypeDef(
                predicate="Operationalizes",
                source_type="KnowHow",
                target_type="Insight",
                polarity="support",
            ),
        ],
        "stored_queries": [
            StoredQueryDef(
                name="contradicted_patterns",
                label="Contradicted Patterns",
                description="Patterns that have contradicting market signals.",
                gq_source=(
                    "query contradicted_patterns() {\n"
                    "  match { $s: Signal; $p: Pattern; $s ContradictsPattern $p }\n"
                    "  return { $p.slug, $p.name, $s.headline }\n"
                    "}"
                ),
            ),
            StoredQueryDef(
                name="emerging_patterns",
                label="Emerging Patterns",
                description="Patterns backed by supporting signals and insights.",
                gq_source=(
                    "query emerging_patterns() {\n"
                    "  match { $s: Signal; $p: Pattern; $s FormsPattern $p }\n"
                    "  return { $p.slug, $p.name, $s.headline }\n"
                    "}"
                ),
            ),
            StoredQueryDef(
                name="recent_signals",
                label="Recent Signals",
                description="All observed SPIKE signals and their linked elements.",
                gq_source=(
                    "query recent_signals() {\n"
                    "  match { $s: Signal }\n"
                    "  return { $s.slug, $s.headline }\n"
                    "}"
                ),
            ),
        ],
        "seed": {
            "nodes": [
                {
                    "node_type": "Element",
                    "slug": "el-local-gguf",
                    "name": "Local GGUF / llama.cpp Runtime",
                    "summary": "On-device quantized inference and embedding execution on Apple Silicon and Linux.",
                },
                {
                    "node_type": "Element",
                    "slug": "el-lance-graph",
                    "name": "Lance Graph Storage",
                    "summary": "Object-storage-native columnar format with zero-copy branching.",
                },
                {
                    "node_type": "Signal",
                    "slug": "sig-hybrid-rrf",
                    "name": "Hybrid BM25 + Graph traversal outperforms flat vector RAG on multi-hop benchmarks",
                    "summary": "Benchmarks show 38% fewer hallucinated links when combining typed edges with BM25.",
                },
                {
                    "node_type": "Signal",
                    "slug": "sig-prompt-bloat",
                    "name": "Unbounded memory injection degrades reasoning accuracy past 2,500 tokens",
                    "summary": "Dumping raw transcripts into system prompts dilutes attention on tool schemas.",
                },
                {
                    "node_type": "Pattern",
                    "slug": "pat-progressive-memory",
                    "name": "Progressive Disclosure Memory Architecture",
                    "summary": "Keep a frozen ~500-token index in the prompt and pull deep graph/wiki context via tools.",
                },
                {
                    "node_type": "Insight",
                    "slug": "ins-branch-before-merge",
                    "name": "Agents need git-style branches for speculative knowledge writes",
                    "summary": "Isolating unverified extractions on review branches prevents silent graph corruption.",
                },
                {
                    "node_type": "KnowHow",
                    "slug": "kh-frozen-snapshot",
                    "name": "Freeze USER.md + MEMORY.md at session start to preserve KV prefix cache",
                    "summary": "Write updates to disk live, but keep the system prompt prefix byte-stable mid-session.",
                },
            ],
            "edges": [
                {
                    "source_id": "Signal:sig-hybrid-rrf",
                    "target_id": "Pattern:pat-progressive-memory",
                    "predicate": "FormsPattern",
                    "polarity": "support",
                    "summary": "Hybrid retrieval enables small prompt footprints.",
                },
                {
                    "source_id": "Signal:sig-prompt-bloat",
                    "target_id": "Pattern:pat-progressive-memory",
                    "predicate": "ContradictsPattern",
                    "polarity": "contradict",
                    "summary": "Demonstrates failure mode when memory is not bounded.",
                },
                {
                    "source_id": "Insight:ins-branch-before-merge",
                    "target_id": "Pattern:pat-progressive-memory",
                    "predicate": "HighlightsPattern",
                    "polarity": "support",
                    "summary": "Branching keeps the curated main branch clean.",
                },
                {
                    "source_id": "KnowHow:kh-frozen-snapshot",
                    "target_id": "Insight:ins-branch-before-merge",
                    "predicate": "Operationalizes",
                    "polarity": "support",
                    "summary": "Combines prefix-cache stability with governed writes.",
                },
            ],
        },
    },
    "pharma-intel": {
        "id": "pharma-intel",
        "number": "02",
        "name": "Pharma intel",
        "tagline": "Monitor trials, filings, competitors, and market movement in a graph built for competitive intelligence.",
        "description": (
            "Three-layer biopharma ontology connecting External Pipeline (compounds, mechanisms, trials) "
            "and SPIKE signals to your Internal Thesis (programs, assumptions, and decisions)."
        ),
        "default_for": "Competitive pipeline & clinical strategy",
        "layers": [
            OntologyLayerDef(
                id="external",
                label="Layer 1 · External Pipeline",
                description="Compounds, mechanisms of action, clinical trials, and sponsors.",
                node_types=["Compound", "Mechanism", "Trial", "Company"],
            ),
            OntologyLayerDef(
                id="spike",
                label="Layer 2 · SPIKE Market Signals",
                description="Clinical readouts, regulatory actions, and competitive patterns.",
                node_types=["Signal", "Pattern", "Insight"],
            ),
            OntologyLayerDef(
                id="internal",
                label="Layer 3 · Internal Thesis & Decisions",
                description="Your programs, core assumptions, upcoming decisions, and open questions.",
                node_types=["Program", "Assumption", "Decision", "OpenQuestion"],
            ),
        ],
        "node_types": [
            OntologyNodeTypeDef(
                name="Compound",
                layer="external",
                color="blue",
                description="Therapeutic candidate or approved drug.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                    _prop("modality", optional=True),
                    _prop("phase", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Mechanism",
                layer="external",
                color="teal",
                description="Biological target or mechanism of action.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                    _prop("target", optional=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Trial",
                layer="external",
                color="indigo",
                description="Clinical trial (NCT ID, phase, status, endpoint).",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("nct_id", is_indexed=True),
                    _prop("status", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Company",
                layer="external",
                color="gray",
                description="Biotech or pharma sponsor.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                    _prop("ticker", optional=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Signal",
                layer="spike",
                color="amber",
                description="Dated clinical readout, safety signal, or filing fact.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("headline", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Pattern",
                layer="spike",
                color="violet",
                description="Competitive or clinical dynamic across programs.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Insight",
                layer="spike",
                color="green",
                description="Strategic takeaway for portfolio positioning.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("title", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Program",
                layer="internal",
                color="pink",
                description="Internal R&D program under governance.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Assumption",
                layer="internal",
                color="orange",
                description="Thesis assumption that internal decisions depend on.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("statement", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Decision",
                layer="internal",
                color="red",
                description="Upcoming go/no-go or trial design gate.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("title", is_indexed=True),
                    _prop("target_date", optional=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="OpenQuestion",
                layer="internal",
                color="teal",
                description="Unresolved clinical or commercial question.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("question", is_indexed=True),
                ],
            ),
        ],
        "edge_types": [
            OntologyEdgeTypeDef(
                predicate="TargetsMechanism",
                source_type="Compound",
                target_type="Mechanism",
                polarity="neutral",
            ),
            OntologyEdgeTypeDef(
                predicate="InvestigatesCompound",
                source_type="Trial",
                target_type="Compound",
                polarity="neutral",
            ),
            OntologyEdgeTypeDef(
                predicate="SupportsAssumption",
                source_type="Signal",
                target_type="Assumption",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="ContradictsAssumption",
                source_type="Signal",
                target_type="Assumption",
                polarity="contradict",
            ),
            OntologyEdgeTypeDef(
                predicate="DecisionBasedOnAssumption",
                source_type="Decision",
                target_type="Assumption",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="InformsQuestion",
                source_type="Signal",
                target_type="OpenQuestion",
                polarity="support",
            ),
        ],
        "stored_queries": [
            StoredQueryDef(
                name="signals_contradicting_assumptions",
                label="Signals Contradicting Assumptions",
                description="External clinical/market signals that challenge internal thesis assumptions.",
                gq_source=(
                    "query signals_contradicting_assumptions() {\n"
                    "  match { $s: Signal; $a: Assumption; $s ContradictsAssumption $a }\n"
                    "  return { $a.slug, $a.statement, $s.headline }\n"
                    "}"
                ),
            ),
            StoredQueryDef(
                name="decisions_at_risk",
                label="Decisions at Risk",
                description="Upcoming program decisions resting on contested assumptions.",
                gq_source=(
                    "query decisions_at_risk() {\n"
                    "  match {\n"
                    "    $d: Decision; $a: Assumption; $s: Signal;\n"
                    "    $d DecisionBasedOnAssumption $a;\n"
                    "    $s ContradictsAssumption $a\n"
                    "  }\n"
                    "  return { $d.title, $a.statement, $s.headline }\n"
                    "}"
                ),
            ),
            StoredQueryDef(
                name="pipeline_by_mechanism",
                label="Pipeline by Mechanism",
                description="Compounds and trials grouped by target mechanism.",
                gq_source=(
                    "query pipeline_by_mechanism() {\n"
                    "  match { $c: Compound; $m: Mechanism; $c TargetsMechanism $m }\n"
                    "  return { $c.name, $m.name }\n"
                    "}"
                ),
            ),
        ],
        "seed": {
            "nodes": [
                {
                    "node_type": "Mechanism",
                    "slug": "mech-glp1-gip",
                    "name": "GLP-1 / GIP Dual Agonist",
                    "summary": "Incretin dual receptor agonism for metabolic weight loss.",
                },
                {
                    "node_type": "Compound",
                    "slug": "cmp-vk2735-oral",
                    "name": "VK2735 Oral",
                    "summary": "Phase 2 oral tablet formulation of dual GLP-1/GIP agonist.",
                },
                {
                    "node_type": "Trial",
                    "slug": "nct-vanquish",
                    "name": "VANQUISH Phase 3 (NCT05930405)",
                    "summary": "Registrational obesity trial evaluating weight reduction at 72 weeks.",
                },
                {
                    "node_type": "Program",
                    "slug": "prog-oral-incretin",
                    "name": "Oral Incretin Expansion Program",
                    "summary": "Primary-care oral maintenance and induction program.",
                },
                {
                    "node_type": "Assumption",
                    "slug": "asm-oral-tolerability",
                    "name": "Oral small-molecule & peptide GLP-1s achieve <10% GI discontinuation at high dose",
                    "summary": "Core thesis required for primary-care adoption without slow titration.",
                },
                {
                    "node_type": "Signal",
                    "slug": "sig-vk2735-p2-clean",
                    "name": "VK2735 13-week oral cohort showed 12.2% weight loss with mild GI profile",
                    "summary": "Placebo-like nausea rate during 4-week titration window.",
                },
                {
                    "node_type": "Signal",
                    "slug": "sig-competitor-gi-dropouts",
                    "name": "Competitor oral small-molecule GLP-1 reported 22% vomiting rate in fast-titration arm",
                    "summary": "High Cmax spike in non-peptide oral class triggered dose-limiting GI events.",
                },
                {
                    "node_type": "Decision",
                    "slug": "dec-p3-oral-start",
                    "name": "Phase 3 Oral Regimen Dose & Titration Lock",
                    "summary": "Gate decision on 4-week vs 8-week titration schedule.",
                },
            ],
            "edges": [
                {
                    "source_id": "Compound:cmp-vk2735-oral",
                    "target_id": "Mechanism:mech-glp1-gip",
                    "predicate": "TargetsMechanism",
                    "polarity": "neutral",
                    "summary": "Dual GLP-1/GIP receptor agonist.",
                },
                {
                    "source_id": "Trial:nct-vanquish",
                    "target_id": "Compound:cmp-vk2735-oral",
                    "predicate": "InvestigatesCompound",
                    "polarity": "neutral",
                    "summary": "Pivotal clinical evaluation.",
                },
                {
                    "source_id": "Signal:sig-vk2735-p2-clean",
                    "target_id": "Assumption:asm-oral-tolerability",
                    "predicate": "SupportsAssumption",
                    "polarity": "support",
                    "summary": "Supports low discontinuation rate for peptide oral formulation.",
                },
                {
                    "source_id": "Signal:sig-competitor-gi-dropouts",
                    "target_id": "Assumption:asm-oral-tolerability",
                    "predicate": "ContradictsAssumption",
                    "polarity": "contradict",
                    "summary": "Challenges fast-titration tolerability across oral class.",
                },
                {
                    "source_id": "Decision:dec-p3-oral-start",
                    "target_id": "Assumption:asm-oral-tolerability",
                    "predicate": "DecisionBasedOnAssumption",
                    "polarity": "support",
                    "summary": "Titration schedule depends on GI tolerability ceiling.",
                },
            ],
        },
    },
    "context-graph": {
        "id": "context-graph",
        "number": "03",
        "name": "Context graph",
        "tagline": "Model decisions, traces, actors, and artifacts so an organization becomes queryable by agents.",
        "description": (
            "Shared organizational memory of record: who owns what, what was claimed in sources, "
            "which claims contradict, and which decisions rest on those claims."
        ),
        "default_for": "Team decisions, specs & project management",
        "layers": [
            OntologyLayerDef(
                id="org",
                label="Layer 1 · People, Teams & Projects",
                description="Actors, teams, and workstreams.",
                node_types=["Person", "Team", "Project"],
            ),
            OntologyLayerDef(
                id="evidence",
                label="Layer 2 · Sources & Claims",
                description="Documents, threads, and attributed claims with exact quotes.",
                node_types=["Source", "Claim"],
            ),
            OntologyLayerDef(
                id="commitments",
                label="Layer 3 · Decisions & Action Items",
                description="Decisions grounded in claims and follow-up commitments.",
                node_types=["Decision", "ActionItem"],
            ),
        ],
        "node_types": [
            OntologyNodeTypeDef(
                name="Person",
                layer="org",
                color="blue",
                description="Team member or stakeholder.",
                properties=[_prop("slug", is_key=True), _prop("name", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Team",
                layer="org",
                color="teal",
                description="Organizational unit or working group.",
                properties=[_prop("slug", is_key=True), _prop("name", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Project",
                layer="org",
                color="indigo",
                description="Initiative or product deliverable.",
                properties=[_prop("slug", is_key=True), _prop("name", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Source",
                layer="evidence",
                color="gray",
                description="Meeting transcript, RFC, PR, or Slack thread.",
                properties=[_prop("slug", is_key=True), _prop("title", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Claim",
                layer="evidence",
                color="violet",
                description="Factual assertion quoted from a source.",
                properties=[_prop("slug", is_key=True), _prop("statement", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Decision",
                layer="commitments",
                color="green",
                description="Recorded decision backed by claims.",
                properties=[_prop("slug", is_key=True), _prop("title", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="ActionItem",
                layer="commitments",
                color="orange",
                description="Tracked follow-up task assigned to an owner.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("title", is_indexed=True),
                    _prop("status", is_indexed=True),
                ],
            ),
        ],
        "edge_types": [
            OntologyEdgeTypeDef(
                predicate="BasedOn",
                source_type="Decision",
                target_type="Claim",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="Contradicts",
                source_type="Claim",
                target_type="Claim",
                polarity="contradict",
            ),
            OntologyEdgeTypeDef(
                predicate="FromSource",
                source_type="Claim",
                target_type="Source",
                polarity="neutral",
            ),
            OntologyEdgeTypeDef(
                predicate="FollowsFrom",
                source_type="ActionItem",
                target_type="Decision",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="AssignedTo",
                source_type="ActionItem",
                target_type="Person",
                polarity="neutral",
            ),
        ],
        "stored_queries": [
            StoredQueryDef(
                name="current_decisions",
                label="Current Decisions",
                description="All active decisions and the claims they rest on.",
                gq_source=(
                    "query current_decisions() {\n"
                    "  match { $d: Decision; $c: Claim; $d BasedOn $c }\n"
                    "  return { $d.title, $c.statement }\n"
                    "}"
                ),
            ),
            StoredQueryDef(
                name="contested_claims",
                label="Contested Claims",
                description="Claims that directly contradict another recorded claim.",
                gq_source=(
                    "query contested_claims() {\n"
                    "  match { $a: Claim; $b: Claim; $a Contradicts $b }\n"
                    "  return { $a.statement, $b.statement }\n"
                    "}"
                ),
            ),
            StoredQueryDef(
                name="open_action_items",
                label="Open Action Items",
                description="Action items following from decisions.",
                gq_source=(
                    "query open_action_items() {\n"
                    "  match { $a: ActionItem }\n"
                    "  return { $a.slug, $a.title }\n"
                    "}"
                ),
            ),
        ],
        "seed": {
            "nodes": [
                {
                    "node_type": "Project",
                    "slug": "proj-local-memory",
                    "name": "Sandwalk Local Memory & Graph Engine",
                    "summary": "Self-hosted memory, wiki, and Omnigraph integration.",
                },
                {
                    "node_type": "Claim",
                    "slug": "clm-sqlite-zero-conf",
                    "name": "Zero-config local SQLite + Markdown must work before any optional binary install",
                    "summary": "Every user gets instant memory and wiki on first launch.",
                },
                {
                    "node_type": "Claim",
                    "slug": "clm-full-prompt-rag",
                    "name": "Injecting all project notes directly into the system prompt is sufficient",
                    "summary": "Early assumption from prototype phase.",
                },
                {
                    "node_type": "Decision",
                    "slug": "dec-frozen-snapshot-plus-tools",
                    "name": "Use Frozen 2,200-char Snapshot + On-Demand Wiki/Graph Tools",
                    "summary": "Preserves prefix cache while scaling to thousands of graph nodes.",
                },
                {
                    "node_type": "ActionItem",
                    "slug": "act-ship-persona-drawer",
                    "name": "Add right-side Profile & Memories drawer to Specialists UI",
                    "summary": "Let users inspect and edit each persona's brain in one click.",
                },
            ],
            "edges": [
                {
                    "source_id": "Claim:clm-sqlite-zero-conf",
                    "target_id": "Claim:clm-full-prompt-rag",
                    "predicate": "Contradicts",
                    "polarity": "contradict",
                    "summary": "Full prompt dumps break token budgets and prefix caching.",
                },
                {
                    "source_id": "Decision:dec-frozen-snapshot-plus-tools",
                    "target_id": "Claim:clm-sqlite-zero-conf",
                    "predicate": "BasedOn",
                    "polarity": "support",
                    "summary": "Combines zero-config startup with bounded prompt budgets.",
                },
                {
                    "source_id": "ActionItem:act-ship-persona-drawer",
                    "target_id": "Decision:dec-frozen-snapshot-plus-tools",
                    "predicate": "FollowsFrom",
                    "polarity": "support",
                    "summary": "Exposes persona memories and priors in the UI.",
                },
            ],
        },
    },
    "vc-os": {
        "id": "vc-os",
        "number": "04",
        "name": "VC OS",
        "tagline": "Connect deal flow, theses, founders, portfolio signals, and follow-up work.",
        "description": (
            "Investment operating graph linking founders, companies, deals, and market signals "
            "against your explicit investment beliefs."
        ),
        "default_for": "Venture, BD & portfolio diligence",
        "layers": [
            OntologyLayerDef(
                id="network",
                label="Layer 1 · Founders, Companies & Deals",
                description="Organizations, people, and active diligence opportunities.",
                node_types=["Organization", "Person", "Deal"],
            ),
            OntologyLayerDef(
                id="thesis",
                label="Layer 2 · Investment Beliefs & Signals",
                description="Core theses and the market/diligence signals testing them.",
                node_types=["InvestmentBelief", "Signal"],
            ),
            OntologyLayerDef(
                id="workflow",
                label="Layer 3 · Meetings & Follow-Ups",
                description="Touchpoints and diligence action items.",
                node_types=["Meeting", "ActionItem"],
            ),
        ],
        "node_types": [
            OntologyNodeTypeDef(
                name="Organization",
                layer="network",
                color="blue",
                description="Startup, portfolio company, or co-investor.",
                properties=[_prop("slug", is_key=True), _prop("name", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Person",
                layer="network",
                color="teal",
                description="Founder, operator, or domain expert.",
                properties=[_prop("slug", is_key=True), _prop("name", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Deal",
                layer="network",
                color="indigo",
                description="Financing round or partnership opportunity.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                    _prop("stage", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="InvestmentBelief",
                layer="thesis",
                color="violet",
                description="Explicit thesis statement guiding capital allocation.",
                properties=[_prop("slug", is_key=True), _prop("thesis", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Signal",
                layer="thesis",
                color="amber",
                description="Customer traction, benchmark, or competitive data point.",
                properties=[_prop("slug", is_key=True), _prop("headline", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Meeting",
                layer="workflow",
                color="gray",
                description="Founder pitch or reference call.",
                properties=[_prop("slug", is_key=True), _prop("title", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="ActionItem",
                layer="workflow",
                color="green",
                description="Diligence follow-up task.",
                properties=[_prop("slug", is_key=True), _prop("title", is_indexed=True)],
            ),
        ],
        "edge_types": [
            OntologyEdgeTypeDef(
                predicate="SupportsBelief",
                source_type="Signal",
                target_type="InvestmentBelief",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="ChallengesBelief",
                source_type="Signal",
                target_type="InvestmentBelief",
                polarity="contradict",
            ),
            OntologyEdgeTypeDef(
                predicate="ThesisForDeal",
                source_type="Deal",
                target_type="InvestmentBelief",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="CompanyDeal",
                source_type="Deal",
                target_type="Organization",
                polarity="neutral",
            ),
        ],
        "stored_queries": [
            StoredQueryDef(
                name="signals_testing_beliefs",
                label="Signals Testing Beliefs",
                description="Signals that support or challenge investment theses.",
                gq_source=(
                    "query signals_testing_beliefs() {\n"
                    "  match { $s: Signal; $b: InvestmentBelief }\n"
                    "  return { $b.thesis, $s.headline }\n"
                    "}"
                ),
            ),
            StoredQueryDef(
                name="active_deals",
                label="Active Deals",
                description="Deals and their linked organizations.",
                gq_source=(
                    "query active_deals() {\n"
                    "  match { $d: Deal }\n"
                    "  return { $d.slug, $d.name }\n"
                    "}"
                ),
            ),
        ],
        "seed": {
            "nodes": [
                {
                    "node_type": "InvestmentBelief",
                    "slug": "bel-local-bio-agents",
                    "name": "Local-first scientific agent harnesses will win wet-lab + dry-lab R&D",
                    "summary": "Biotech IP privacy + local GPU/cluster execution beats cloud-only chat.",
                },
                {
                    "node_type": "Signal",
                    "slug": "sig-pharma-onprem",
                    "name": "Top-20 pharma teams block unredacted assay data from consumer cloud chatbots",
                    "summary": "Security policies require local or VPC-isolated agent state.",
                },
                {
                    "node_type": "Deal",
                    "slug": "deal-seed-bioos",
                    "name": "BioOS Seed Diligence",
                    "summary": "Evaluating wet-lab automation + structure prediction stack.",
                },
            ],
            "edges": [
                {
                    "source_id": "Signal:sig-pharma-onprem",
                    "target_id": "InvestmentBelief:bel-local-bio-agents",
                    "predicate": "SupportsBelief",
                    "polarity": "support",
                    "summary": "Validates enterprise pull for local-first architecture.",
                },
                {
                    "source_id": "Deal:deal-seed-bioos",
                    "target_id": "InvestmentBelief:bel-local-bio-agents",
                    "predicate": "ThesisForDeal",
                    "polarity": "support",
                    "summary": "Core thesis behind the diligence.",
                },
            ],
        },
    },
    "biomed-research": {
        "id": "biomed-research",
        "number": "05",
        "name": "Biomed research",
        "tagline": "Track papers, claims, entities, and evidence across biotech and medical research.",
        "description": (
            "Canonical scientific discovery graph connecting genes, proteins, compounds, "
            "diseases, papers, datasets, and assay results with supporting vs. contradicting claims."
        ),
        "default_for": "Scientific & bioinformatics projects (Default)",
        "layers": [
            OntologyLayerDef(
                id="entities",
                label="Layer 1 · Biological & Chemical Entities",
                description="Genes, proteins, compounds, diseases, and cell lines.",
                node_types=["Entity"],
            ),
            OntologyLayerDef(
                id="evidence",
                label="Layer 2 · Literature, Datasets & Assays",
                description="Primary papers (PMID/DOI), DepMap/PRISM datasets, and wet/dry-lab assay runs.",
                node_types=["Paper", "Dataset", "AssayResult"],
            ),
            OntologyLayerDef(
                id="claims",
                label="Layer 3 · Hypotheses & Evidence Claims",
                description="Testable hypotheses and polarity-scored claims (Supports vs Contradicts).",
                node_types=["Hypothesis", "Claim"],
            ),
        ],
        "node_types": [
            OntologyNodeTypeDef(
                name="Entity",
                layer="entities",
                color="blue",
                description="Normalized bioentity (gene:KRAS, compound:MRTX1133, disease:PDAC).",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                    _prop("entity_type", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Paper",
                layer="evidence",
                color="teal",
                description="Peer-reviewed publication or preprint (PMID / DOI).",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("title", is_indexed=True),
                    _prop("pmid", optional=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Dataset",
                layer="evidence",
                color="indigo",
                description="Omics, CRISPR, or chemical screen dataset.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="AssayResult",
                layer="evidence",
                color="amber",
                description="Experimental readout, docking score, or DESeq2/DepMap analysis.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("name", is_indexed=True),
                    _prop("metric", optional=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Hypothesis",
                layer="claims",
                color="violet",
                description=" Mechanistic or therapeutic hypothesis under investigation.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("statement", is_indexed=True),
                ],
            ),
            OntologyNodeTypeDef(
                name="Claim",
                layer="claims",
                color="green",
                description="Structured scientific assertion linking entities and evidence.",
                properties=[
                    _prop("slug", is_key=True),
                    _prop("statement", is_indexed=True),
                ],
            ),
        ],
        "edge_types": [
            OntologyEdgeTypeDef(
                predicate="Supports",
                source_type="AssayResult",
                target_type="Hypothesis",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="Contradicts",
                source_type="AssayResult",
                target_type="Hypothesis",
                polarity="contradict",
            ),
            OntologyEdgeTypeDef(
                predicate="PaperSupports",
                source_type="Paper",
                target_type="Claim",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="PaperContradicts",
                source_type="Paper",
                target_type="Claim",
                polarity="contradict",
            ),
            OntologyEdgeTypeDef(
                predicate="Targets",
                source_type="Entity",
                target_type="Entity",
                polarity="neutral",
            ),
            OntologyEdgeTypeDef(
                predicate="AboutEntity",
                source_type="Claim",
                target_type="Entity",
                polarity="neutral",
            ),
        ],
        "stored_queries": [
            StoredQueryDef(
                name="contested_claims",
                label="Contested Hypotheses & Claims",
                description="Hypotheses or claims that have contradicting experimental or literature evidence.",
                gq_source=(
                    "query contested_claims() {\n"
                    "  match { $a: AssayResult; $h: Hypothesis; $a Contradicts $h }\n"
                    "  return { $h.slug, $h.statement, $a.name }\n"
                    "}"
                ),
            ),
            StoredQueryDef(
                name="evidence_for_target",
                label="Supporting Evidence Matrix",
                description="All assay results and papers supporting active hypotheses.",
                gq_source=(
                    "query evidence_for_target() {\n"
                    "  match { $a: AssayResult; $h: Hypothesis; $a Supports $h }\n"
                    "  return { $h.statement, $a.name }\n"
                    "}"
                ),
            ),
            StoredQueryDef(
                name="recent_lab_findings",
                label="Recent Lab & Omics Findings",
                description="All biological entities, assays, and claims in the current graph.",
                gq_source=(
                    "query recent_lab_findings() {\n"
                    "  match { $e: Entity }\n"
                    "  return { $e.slug, $e.name }\n"
                    "}"
                ),
            ),
        ],
        "seed": {
            "nodes": [
                {
                    "node_type": "Entity",
                    "slug": "gene-kras-g12d",
                    "name": "KRAS G12D",
                    "summary": "Oncogenic GTPase driver mutation prevalent in PDAC and CRC.",
                },
                {
                    "node_type": "Entity",
                    "slug": "cmp-mrtx1133",
                    "name": "MRTX1133",
                    "summary": "Selective non-covalent KRAS G12D inhibitor.",
                },
                {
                    "node_type": "Entity",
                    "slug": "gene-egfr",
                    "name": "EGFR / ERBB1",
                    "summary": "Receptor tyrosine kinase mediating adaptive feedback reactivation.",
                },
                {
                    "node_type": "Dataset",
                    "slug": "ds-depmap-24q4",
                    "name": "DepMap 24Q4 CRISPR + PRISM",
                    "summary": "Lineage dependency and compound viability across PDAC lines.",
                },
                {
                    "node_type": "AssayResult",
                    "slug": "assay-pdac-monotherapy",
                    "name": "PRISM Viability: MRTX1133 picomolar potency in AsPC-1 (IC50 = 1.8 nM)",
                    "summary": "Strong acute growth arrest in 3D spheroid culture at 48h.",
                },
                {
                    "node_type": "AssayResult",
                    "slug": "assay-rtk-rebound-72h",
                    "name": "Phospho-proteomics 72h: pERK rebound driven by EGFR/SHP2 feedback in 4/6 PDAC lines",
                    "summary": "Single-agent durability stalls after 72h due to wild-type RAS reactivation.",
                },
                {
                    "node_type": "Paper",
                    "slug": "pmid-36812401",
                    "name": "Hallin et al. Nature Medicine — Anti-tumor efficacy of MRTX1133",
                    "summary": "Demonstrates deep regression and synergy with EGFR blockade.",
                },
                {
                    "node_type": "Hypothesis",
                    "slug": "hyp-mrtx1133-mono-durable",
                    "name": "MRTX1133 monotherapy achieves durable complete regression in KRAS-G12D PDAC",
                    "summary": "Initial single-agent clinical hypothesis.",
                },
                {
                    "node_type": "Claim",
                    "slug": "clm-dual-egfr-kras-synergy",
                    "name": "Co-targeting EGFR + KRAS-G12D prevents pERK rebound and restores apoptosis",
                    "summary": "Combination thesis supported by phospho-proteomics and xenografts.",
                },
            ],
            "edges": [
                {
                    "source_id": "Entity:cmp-mrtx1133",
                    "target_id": "Entity:gene-kras-g12d",
                    "predicate": "Targets",
                    "polarity": "neutral",
                    "summary": "Binds Switch-II pocket of GDP/GTP KRAS G12D.",
                },
                {
                    "source_id": "AssayResult:assay-pdac-monotherapy",
                    "target_id": "Hypothesis:hyp-mrtx1133-mono-durable",
                    "predicate": "Supports",
                    "polarity": "support",
                    "summary": "Acute 48h spheroid potency supports initial activity.",
                },
                {
                    "source_id": "AssayResult:assay-rtk-rebound-72h",
                    "target_id": "Hypothesis:hyp-mrtx1133-mono-durable",
                    "predicate": "Contradicts",
                    "polarity": "contradict",
                    "summary": "72h pERK rebound contradicts durable monotherapy response.",
                },
                {
                    "source_id": "Paper:pmid-36812401",
                    "target_id": "Claim:clm-dual-egfr-kras-synergy",
                    "predicate": "PaperSupports",
                    "polarity": "support",
                    "summary": "Cetuximab + MRTX1133 combination overcomes adaptive resistance.",
                },
                {
                    "source_id": "Claim:clm-dual-egfr-kras-synergy",
                    "target_id": "Entity:gene-egfr",
                    "predicate": "AboutEntity",
                    "polarity": "neutral",
                    "summary": "Identifies EGFR as primary bypass node.",
                },
            ],
        },
    },
    "second-brain": {
        "id": "second-brain",
        "number": "06",
        "name": "Second brain",
        "tagline": "A personal operating graph for notes, people, commitments, routines, and recurring work.",
        "description": (
            "Personal knowledge ontology linking people, organizations, notes, tasks, "
            "projects, and long-term goals."
        ),
        "default_for": "Global personal memory & notes (Default Global)",
        "layers": [
            OntologyLayerDef(
                id="people",
                label="Layer 1 · People & Organizations",
                description="Collaborators, labs, teams, and relationships.",
                node_types=["Person", "Organization"],
            ),
            OntologyLayerDef(
                id="capture",
                label="Layer 2 · Notes & Artifacts",
                description="Synthesized notes, papers, and saved artifacts.",
                node_types=["Note", "Artifact"],
            ),
            OntologyLayerDef(
                id="action",
                label="Layer 3 · Goals, Projects & Tasks",
                description="Active objectives, recurring routines, and next actions.",
                node_types=["Goal", "Project", "Task"],
            ),
        ],
        "node_types": [
            OntologyNodeTypeDef(
                name="Person",
                layer="people",
                color="blue",
                description="Collaborator, mentor, or teammate.",
                properties=[_prop("slug", is_key=True), _prop("name", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Organization",
                layer="people",
                color="teal",
                description="Company, lab, or institution.",
                properties=[_prop("slug", is_key=True), _prop("name", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Note",
                layer="capture",
                color="violet",
                description="Evergreen note or synthesis.",
                properties=[_prop("slug", is_key=True), _prop("title", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Artifact",
                layer="capture",
                color="indigo",
                description="Document, script, or dataset reference.",
                properties=[_prop("slug", is_key=True), _prop("title", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Goal",
                layer="action",
                color="green",
                description="Long-horizon objective.",
                properties=[_prop("slug", is_key=True), _prop("title", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Project",
                layer="action",
                color="amber",
                description="Active workstream advancing a goal.",
                properties=[_prop("slug", is_key=True), _prop("name", is_indexed=True)],
            ),
            OntologyNodeTypeDef(
                name="Task",
                layer="action",
                color="orange",
                description="Concrete next action.",
                properties=[_prop("slug", is_key=True), _prop("title", is_indexed=True)],
            ),
        ],
        "edge_types": [
            OntologyEdgeTypeDef(
                predicate="AdvancesGoal",
                source_type="Project",
                target_type="Goal",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="InformsProject",
                source_type="Note",
                target_type="Project",
                polarity="support",
            ),
            OntologyEdgeTypeDef(
                predicate="TaskForProject",
                source_type="Task",
                target_type="Project",
                polarity="neutral",
            ),
            OntologyEdgeTypeDef(
                predicate="WorksWith",
                source_type="Person",
                target_type="Organization",
                polarity="neutral",
            ),
            OntologyEdgeTypeDef(
                predicate="ContradictsGoal",
                source_type="Task",
                target_type="Goal",
                polarity="contradict",
            ),
        ],
        "stored_queries": [
            StoredQueryDef(
                name="active_goals_and_tasks",
                label="Active Goals & Projects",
                description="Projects and notes advancing your top goals.",
                gq_source=(
                    "query active_goals_and_tasks() {\n"
                    "  match { $p: Project; $g: Goal; $p AdvancesGoal $g }\n"
                    "  return { $g.title, $p.name }\n"
                    "}"
                ),
            ),
            StoredQueryDef(
                name="notes_by_topic",
                label="Connected Notes",
                description="Notes informing active projects.",
                gq_source=(
                    "query notes_by_topic() {\n"
                    "  match { $n: Note }\n"
                    "  return { $n.slug, $n.title }\n"
                    "}"
                ),
            ),
            StoredQueryDef(
                name="contested_commitments",
                label="Bottlenecks & Contradictions",
                description="Tasks or anti-patterns that conflict with active goals.",
                gq_source=(
                    "query contested_commitments() {\n"
                    "  match { $t: Task; $g: Goal; $t ContradictsGoal $g }\n"
                    "  return { $t.title, $g.title }\n"
                    "}"
                ),
            ),
        ],
        "seed": {
            "nodes": [
                {
                    "node_type": "Goal",
                    "slug": "goal-autonomous-rd",
                    "name": "Build an compounding local R&D brain across sessions",
                    "summary": "Every agent run leaves behind reusable Wiki pages, Graph claims, and Skills.",
                },
                {
                    "node_type": "Project",
                    "slug": "proj-sandwalk-memory",
                    "name": "Sandwalk Knowledge & Persona System",
                    "summary": "Unified Memory + Living Wiki + Omnigraph Explorer.",
                },
                {
                    "node_type": "Note",
                    "slug": "note-karpathy-wiki",
                    "name": "LLM-maintained Markdown Wikis compound faster than flat chat logs",
                    "summary": "Link pages with [[wikilinks]] and keep a compact TOC in the system prompt.",
                },
            ],
            "edges": [
                {
                    "source_id": "Project:proj-sandwalk-memory",
                    "target_id": "Goal:goal-autonomous-rd",
                    "predicate": "AdvancesGoal",
                    "polarity": "support",
                    "summary": "Core platform milestone.",
                },
                {
                    "source_id": "Note:note-karpathy-wiki",
                    "target_id": "Project:proj-sandwalk-memory",
                    "predicate": "InformsProject",
                    "polarity": "support",
                    "summary": "Architectural principle for the Living Wiki tab.",
                },
            ],
        },
    },
}


def get_cookbook_summary(
    cookbook_id: str,
    *,
    node_counts: dict[str, int] | None = None,
    edge_counts: dict[str, int] | None = None,
) -> CookbookSummary:
    raw = COOKBOOK_DEFINITIONS.get(cookbook_id) or COOKBOOK_DEFINITIONS["biomed-research"]
    n_counts = node_counts or {}
    e_counts = edge_counts or {}
    node_types = [
        nt.model_copy(update={"count": int(n_counts.get(nt.name, 0))})
        for nt in raw["node_types"]
    ]
    edge_types = [
        et.model_copy(update={"count": int(e_counts.get(et.predicate, 0))})
        for et in raw["edge_types"]
    ]
    pg_schema = _render_pg_schema(raw["name"], node_types, edge_types)
    return CookbookSummary(
        id=raw["id"],
        number=raw["number"],
        name=raw["name"],
        tagline=raw["tagline"],
        description=raw["description"],
        default_for=raw["default_for"],
        layers=list(raw["layers"]),
        node_types=node_types,
        edge_types=edge_types,
        stored_queries=list(raw["stored_queries"]),
        pg_schema=pg_schema,
    )


def list_cookbook_summaries() -> list[CookbookSummary]:
    order = [
        "industry-intel",
        "pharma-intel",
        "context-graph",
        "vc-os",
        "biomed-research",
        "second-brain",
    ]
    return [get_cookbook_summary(cid) for cid in order]


def get_cookbook_seed(cookbook_id: str) -> dict[str, list[dict[str, Any]]]:
    raw = COOKBOOK_DEFINITIONS.get(cookbook_id) or COOKBOOK_DEFINITIONS["biomed-research"]
    return dict(raw.get("seed") or {"nodes": [], "edges": []})
