"""chemistry.mmp_analysis: matched molecular pair analysis. Split from tools/chemistry.py."""
from tools import registry
from tools.chemistry_mmp_parse import load_and_parse_compounds


def _compute_matched_pairs(parsed: list) -> tuple[list, dict]:
    """Fragment molecules (BRICS) and identify matched pairs sharing a Murcko scaffold."""
    from rdkit.Chem import BRICS

    fragments_map = {}  # smiles -> list of BRICS fragment SMILES (informational)
    for entry in parsed:
        smi = entry["smiles"]
        fragments_map[smi] = []
        try:
            for frag in BRICS.BRICSDecompose(entry["mol"], returnMols=False):
                fragments_map[smi].append(frag)
        except Exception:
            pass

    scaffold_groups: dict = {}
    for entry in parsed:
        scaffold_groups.setdefault(entry["scaffold"], []).append(entry)

    pairs = []
    transformations: dict = {}  # scaffold -> [{"from", "to", "delta"}]

    for scaffold, members in scaffold_groups.items():
        if len(members) < 2:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                m1, m2 = members[i], members[j]
                delta = m2["activity"] - m1["activity"]

                try:
                    from rdkit.Chem import rdFMCS
                    mcs = rdFMCS.FindMCS([m1["mol"], m2["mol"]], timeout=2, matchValences=True, ringMatchesRingOnly=True)
                    core_smarts = mcs.smartsString if mcs and mcs.numAtoms > 0 else None
                except Exception:
                    core_smarts = None

                atoms1, atoms2 = m1["mol"].GetNumHeavyAtoms(), m2["mol"].GetNumHeavyAtoms()

                pairs.append({
                    "compound_a": m1["smiles"],
                    "compound_b": m2["smiles"],
                    "name_a": m1.get("name", m1["smiles"]),
                    "name_b": m2.get("name", m2["smiles"]),
                    "activity_a": round(m1["activity"], 3),
                    "activity_b": round(m2["activity"], 3),
                    "delta_activity": round(delta, 3),
                    "scaffold": scaffold,
                    "core_mcs": core_smarts,
                    "heavy_atom_diff": atoms2 - atoms1,
                })

                transformations.setdefault(scaffold, []).append({"from": m1["smiles"], "to": m2["smiles"], "delta": delta})

    return pairs, transformations


def _scaffold_stats(transformations: dict) -> list:
    import numpy as np

    stats = []
    for scaffold, trans_list in transformations.items():
        deltas = [t["delta"] for t in trans_list]
        stats.append({
            "scaffold": scaffold,
            "n_pairs": len(trans_list),
            "mean_delta": round(float(np.mean(deltas)), 3),
            "max_delta": round(float(np.max(deltas)), 3),
            "min_delta": round(float(np.min(deltas)), 3),
            "std_delta": round(float(np.std(deltas)), 3) if len(deltas) > 1 else 0.0,
        })
    return stats


@registry.register(
    name="chemistry.mmp_analysis",
    description="Matched molecular pair analysis to identify R-group transformations that improve activity",
    category="chemistry",
    parameters={
        "compounds_csv": "Path to CSV with SMILES and activity columns",
        "activity_col": "Name of the activity column (default 'activity')",
    },
    usage_guide="You have a congeneric series of compounds and want to identify which single-point structural changes drive activity. Use for medicinal chemistry SAR optimization — finds matched molecular pairs and ranks R-group swaps by activity improvement.",
)
def mmp_analysis(compounds_csv: str = None, activity_col: str = "activity", **kwargs) -> dict:
    """Matched molecular pair analysis for a set of compounds.

    Fragments molecules at single acyclic bonds, identifies matched pairs
    (same core, different R-group), and correlates R-group changes with
    activity differences.
    """
    try:
        from rdkit import Chem  # noqa: F401
        from rdkit.Chem import BRICS, AllChem, Descriptors, rdMolDescriptors  # noqa: F401
    except ImportError:
        return {"error": "RDKit is required for MMP analysis. Install with: pip install rdkit", "summary": "RDKit is required for MMP analysis. Install with: pip install rdkit"}

    loaded = load_and_parse_compounds(compounds_csv, activity_col)
    if "error" in loaded:
        return loaded
    parsed, using_demo = loaded["parsed"], loaded["using_demo"]

    pairs, transformations = _compute_matched_pairs(parsed)
    pairs.sort(key=lambda x: abs(x["delta_activity"]), reverse=True)
    scaffold_stats = _scaffold_stats(transformations)

    top_improvements = [p for p in pairs if p["delta_activity"] > 0][:10]
    top_decreases = sorted((p for p in pairs if p["delta_activity"] < 0), key=lambda x: x["delta_activity"])[:5]

    n_scaffolds = len({entry["scaffold"] for entry in parsed})

    summary_lines = [f"MMP analysis: {len(parsed)} compounds, {len(pairs)} matched pairs, {n_scaffolds} scaffold(s)"]
    if using_demo:
        summary_lines.append("(Using built-in demo dataset — provide compounds_csv for custom analysis)")
    if top_improvements:
        best = top_improvements[0]
        summary_lines.append(f"Best improvement: {best['name_a']} -> {best['name_b']} (delta={best['delta_activity']:+.3f})")

    return {
        "summary": "\n".join(summary_lines),
        "n_compounds": len(parsed),
        "n_pairs": len(pairs),
        "n_scaffolds": n_scaffolds,
        "using_demo_data": using_demo,
        "top_improvements": top_improvements,
        "top_decreases": top_decreases,
        "scaffold_stats": scaffold_stats,
        "all_pairs": pairs[:50],
    }
