"""intel — part 2 of split module. See tools/intel.py."""
from __future__ import annotations
from tools.intel_base import registry
from tools.intel_part1 import _to_int

@registry.register(
    name="intel.competitor_snapshot",
    description="Generate a one-shot competitor snapshot for a target and indication",
    category="intel",
    parameters={
        "gene": "Target gene symbol (e.g., LRRK2, IL23R)",
        "indication": "Optional indication filter",
        "max_programs": "Maximum trial/program records to include (default 15)",
    },
    usage_guide=(
        "Use for decision meetings and external positioning. Summarizes active sponsors, phases, "
        "mechanism diversity, and top benchmark endpoints around a target."
    ),
)
def competitor_snapshot(
    gene: str,
    indication: str = "",
    max_programs: int = 15,
    **kwargs,
) -> dict:
    """Build a compact competitor snapshot using clinical and target landscape tools."""
    del kwargs
    if not gene or not gene.strip():
        return {"summary": "gene is required.", "error": "missing_gene"}

    from tools.clinical import competitive_landscape, trial_design_benchmark

    max_programs = max(1, min(int(max_programs or 15), 50))
    landscape = competitive_landscape(gene=gene.strip(), indication=indication.strip())
    benchmark = trial_design_benchmark(
        query=f"{gene} {indication}".strip(),
        max_results=min(100, max_programs * 2),
    )

    if "error" in landscape and "error" in benchmark:
        return {
            "summary": f"Competitor snapshot failed for {gene}: upstream sources unavailable.",
            "error": "snapshot_failed",
            "sources": {
                "landscape_error": landscape.get("error"),
                "benchmark_error": benchmark.get("error"),
            },
        }

    trial_records = ((landscape.get("trials") or {}).get("top_trials") or [])[:max_programs]
    sponsors = {}
    for trial in trial_records:
        sponsor = str(trial.get("sponsor", "")).strip()
        if sponsor:
            sponsors[sponsor] = sponsors.get(sponsor, 0) + 1
    top_sponsors = sorted(sponsors.items(), key=lambda kv: kv[1], reverse=True)[:10]

    phase_dist = ((landscape.get("trials") or {}).get("phase_distribution") or {})
    chembl = (landscape.get("chembl") or {})
    ot = (landscape.get("open_targets") or {})
    top_endpoints = (benchmark.get("top_primary_endpoints") or [])[:5]

    differentiation_flags = []
    if _to_int(phase_dist.get("PHASE3", 0), 0) == 0:
        differentiation_flags.append("No Phase 3 pressure detected in returned trial window.")
    if _to_int(chembl.get("unique_compounds", 0), 0) < 10:
        differentiation_flags.append("Limited small-molecule density; potential white space.")
    if _to_int(ot.get("n_known_drugs", 0), 0) == 0:
        differentiation_flags.append("No known drugs in Open Targets snapshot for this target.")

    summary = (
        f"Competitor snapshot for {gene}{f' in {indication}' if indication else ''}: "
        f"{_to_int((landscape.get('trials') or {}).get('total_count', 0), 0)} trial records, "
        f"{_to_int(chembl.get('unique_compounds', 0), 0)} ChEMBL compounds, "
        f"{_to_int(ot.get('n_known_drugs', 0), 0)} known drugs."
    )

    return {
        "summary": summary,
        "gene": gene,
        "indication": indication or None,
        "top_sponsors": [{"sponsor": name, "trial_count": count} for name, count in top_sponsors],
        "phase_distribution": phase_dist,
        "top_primary_endpoints": top_endpoints,
        "mechanism_classes": sorted(chembl.get("moa_types", []) or []),
        "differentiation_flags": differentiation_flags,
        "programs": trial_records,
        "landscape": landscape,
        "benchmark": benchmark,
    }
