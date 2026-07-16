"""safety anti-target screening tools: antitarget_profile, classify, sall4_risk.

Split from tools/safety.py.
"""

import pandas as pd

from tools import registry
from tools.safety_common import (
    CRBN_SUBSTRATES,
    HEME_TFS,
    TERATOGENIC_SUBSTRATES,
    TUMOR_SUPPRESSORS,
    UNIPROT_TO_GENE,
    _display_name,
    _gene_ids,
)


@registry.register(
    name="safety.antitarget_profile",
    description="Screen degradation data for anti-target hits (tumor suppressors, essential genes, heme TFs)",
    category="safety",
    parameters={
        "compound_id": "Compound to profile (or 'all')",
        "lfc_threshold": "LFC threshold for degradation call (default -0.5)",
    },
    requires_data=["proteomics"],
    usage_guide="You need to check if a compound degrades dangerous off-targets (tumor suppressors, essential heme TFs, teratogenic substrates). Run this first in any safety assessment workflow.",
)
def antitarget_profile(compound_id: str = "all", lfc_threshold: float = -0.5, **kwargs) -> dict:
    """Screen proteomics data for degradation of anti-target proteins.

    Anti-targets: tumor suppressors, essential heme TFs, teratogenic substrates,
    and known CRBN substrates. Degrading these = safety liability.
    """
    from tools._compound_resolver import resolve_compound
    if compound_id != "all":
        compound_id = resolve_compound(compound_id, dataset="proteomics")

    try:
        from data.loaders import load_proteomics
        prot = load_proteomics()
    except FileNotFoundError:
        return {
            "error": "Proteomics data not available.",
            "summary": "Proteomics data not available — skipping. Provide proteomics data for full analysis.",
        }

    compounds = [compound_id] if compound_id != "all" else prot.columns.tolist()
    all_proteins = set(prot.index)

    # Categorize known anti-targets present in data (handles both gene symbols and UniProt IDs)
    tsg_present = _gene_ids(TUMOR_SUPPRESSORS, all_proteins)
    heme_present = _gene_ids(HEME_TFS, all_proteins)
    terat_present = _gene_ids(TERATOGENIC_SUBSTRATES, all_proteins)
    crbn_present = _gene_ids(CRBN_SUBSTRATES, all_proteins)

    results = []
    for cpd in compounds:
        if cpd not in prot.columns:
            continue

        values = prot[cpd].dropna()
        degraded = values[values < lfc_threshold]

        # Check anti-target categories
        hits = {
            "tumor_suppressors": sorted([p for p in degraded.index if p in tsg_present]),
            "heme_tfs": sorted([p for p in degraded.index if p in heme_present]),
            "teratogenic": sorted([p for p in degraded.index if p in terat_present]),
            "crbn_substrates": sorted([p for p in degraded.index if p in crbn_present]),
        }

        n_antitargets = sum(len(v) for v in hits.values())

        # Compute safety penalty score
        penalty = 0.0
        for _p in hits["teratogenic"]:
            penalty += 10.0  # highest risk
        for _p in hits["heme_tfs"]:
            penalty += 5.0
        for _p in hits["tumor_suppressors"]:
            penalty += 3.0
        for _p in hits["crbn_substrates"]:
            penalty += 2.0

        # Get LFC values for flagged proteins
        flagged_details = []
        for category, proteins in hits.items():
            for p in proteins:
                flagged_details.append({
                    "protein": _display_name(p),
                    "protein_id": p,
                    "category": category,
                    "lfc": round(float(values[p]), 3),
                })

        results.append({
            "compound": cpd,
            "n_total_degraded": len(degraded),
            "n_antitargets": n_antitargets,
            "n_tumor_suppressors": len(hits["tumor_suppressors"]),
            "n_heme_tfs": len(hits["heme_tfs"]),
            "n_teratogenic": len(hits["teratogenic"]),
            "n_crbn_substrates": len(hits["crbn_substrates"]),
            "safety_penalty": round(penalty, 1),
            "flagged_proteins": flagged_details,
        })

    df = pd.DataFrame([{k: v for k, v in r.items() if k != "flagged_proteins"} for r in results])
    if len(df) > 0:
        df = df.sort_values("safety_penalty", ascending=False)

    if compound_id != "all":
        r = results[0] if results else {}
        flagged_str = ", ".join([f"{d['protein']}({d['category']})" for d in r.get("flagged_proteins", [])])
        summary = (
            f"Anti-target profile for {compound_id}: "
            f"{r.get('n_antitargets', 0)} anti-targets hit, "
            f"penalty={r.get('safety_penalty', 0)}\n"
            f"Flagged: {flagged_str if flagged_str else 'none'}"
        )
    else:
        n_clean = (df["n_antitargets"] == 0).sum() if len(df) > 0 else 0
        summary = (
            f"Anti-target screening: {len(df)} compounds profiled\n"
            f"Clean (0 anti-targets): {n_clean}/{len(df)}"
        )

    return {
        "summary": summary,
        "n_screened": len(tsg_present | heme_present | terat_present | crbn_present),
        "antitarget_counts": {
            "tumor_suppressors": len(tsg_present),
            "heme_tfs": len(heme_present),
            "teratogenic": len(terat_present),
            "crbn_substrates": len(crbn_present),
        },
        "profiles": results if compound_id != "all" else df.to_dict("records"),
    }


@registry.register(
    name="safety.classify",
    description="Classify compound safety as SAFE/CAUTION/DANGEROUS based on multi-modal profiling",
    category="safety",
    parameters={
        "compound_id": "Compound to classify (or 'all')",
    },
    requires_data=["proteomics", "prism"],
    usage_guide="You need a quick safety verdict (SAFE/CAUTION/DANGEROUS) before advancing a compound. Combines anti-target profile with viability breadth. Run after antitarget_profile for full context.",
)
def classify(compound_id: str = "all", **kwargs) -> dict:
    """Multi-modal safety classification.

    Classification rules:
    - DANGEROUS: degrades any teratogenic substrate OR safety_penalty >= 15
    - CAUTION: degrades tumor suppressors OR heme TFs OR safety_penalty >= 5
    - SAFE: no anti-target degradation AND safety_penalty < 5

    Also considers viability breadth (% cell lines killed) as a toxicity signal.
    """
    # Get anti-target profile (handles missing proteomics internally)
    at_result = antitarget_profile(compound_id=compound_id)
    if "error" in at_result:
        return at_result

    profiles = at_result["profiles"]

    # Get viability breadth from PRISM
    try:
        from data.loaders import load_prism
        prism = load_prism()
    except FileNotFoundError:
        return {
            "error": "PRISM data not available.",
            "summary": "PRISM data not available — skipping. Run: sandwalk data pull prism",
        }

    results = []
    for profile in profiles:
        cpd = profile["compound"]
        penalty = profile["safety_penalty"]

        # Viability breadth
        cpd_data = prism[prism["pert_name"] == cpd]
        breadth = 0.0
        if len(cpd_data) > 0:
            max_dose = cpd_data["pert_dose"].max()
            cpd_hd = cpd_data[cpd_data["pert_dose"] == max_dose]
            per_cell = cpd_hd.groupby("ccle_name")["LFC"].mean()
            breadth = float((per_cell < -0.5).mean())

        # Classification
        if profile["n_teratogenic"] > 0 or penalty >= 15:
            classification = "DANGEROUS"
        elif profile["n_tumor_suppressors"] > 0 or profile["n_heme_tfs"] > 0 or penalty >= 5:
            classification = "CAUTION"
        elif breadth > 0.8:
            classification = "CAUTION"  # kills too many cell lines = nonspecific toxicity
        else:
            classification = "SAFE"

        # Safety score (0-100, higher = safer)
        safety_score = max(0, 100 - penalty * 5 - breadth * 30)

        results.append({
            "compound": cpd,
            "classification": classification,
            "safety_score": round(safety_score, 1),
            "safety_penalty": penalty,
            "viability_breadth": round(breadth, 3),
            "n_antitargets": profile["n_antitargets"],
            "n_tumor_suppressors": profile["n_tumor_suppressors"],
            "n_heme_tfs": profile["n_heme_tfs"],
            "n_teratogenic": profile["n_teratogenic"],
        })

    df = pd.DataFrame(results)

    if len(df) > 0:
        counts = df["classification"].value_counts().to_dict()
        safe = counts.get("SAFE", 0)
        caution = counts.get("CAUTION", 0)
        dangerous = counts.get("DANGEROUS", 0)
    else:
        safe = caution = dangerous = 0

    if compound_id != "all" and results:
        r = results[0]
        summary = (
            f"Safety classification for {compound_id}: {r['classification']}\n"
            f"Score: {r['safety_score']}/100, Penalty: {r['safety_penalty']}, "
            f"Viability breadth: {r['viability_breadth']:.1%}"
        )
    else:
        summary = (
            f"Safety classification: {len(df)} compounds\n"
            f"SAFE: {safe}, CAUTION: {caution}, DANGEROUS: {dangerous}"
        )

    return {
        "summary": summary,
        "classifications": results,
        "distribution": {"SAFE": safe, "CAUTION": caution, "DANGEROUS": dangerous},
    }


@registry.register(
    name="safety.sall4_risk",
    description="Assess SALL4 degradation risk for IMiD-type molecular glue compounds (teratogenicity marker)",
    category="safety",
    parameters={
        "compound_id": "Compound to check (or 'all')",
    },
    requires_data=["proteomics"],
    usage_guide="You are working with CRBN-based molecular glues and need to assess teratogenicity risk. SALL4 degradation was the molecular cause of thalidomide birth defects — critical safety check for any IMiD-type compound.",
)
def sall4_risk(compound_id: str = "all", **kwargs) -> dict:
    """Check for SALL4 degradation -- the key teratogenicity signal for IMiD-type compounds.

    SALL4 is a zinc finger TF essential for limb development. Its degradation by
    thalidomide via CRBN was the molecular cause of thalidomide teratogenicity.
    Any CRBN-based molecular glue that degrades SALL4 is a teratogenicity risk.
    """
    from tools._compound_resolver import resolve_compound
    if compound_id != "all":
        compound_id = resolve_compound(compound_id, dataset="proteomics")

    try:
        from data.loaders import load_proteomics
        prot = load_proteomics()
    except FileNotFoundError:
        return {
            "error": "Proteomics data not available.",
            "summary": "Proteomics data not available — skipping. Provide proteomics data for full analysis.",
        }

    # Check for SALL family proteins (handles both gene symbols and UniProt IDs)
    sall_uniprot = {uid: gene for uid, gene in UNIPROT_TO_GENE.items() if gene.startswith("SALL")}
    sall_proteins = []  # list of (index_id, gene_symbol)
    for p in prot.index:
        if p.startswith("SALL"):
            sall_proteins.append((p, p))
        elif p in sall_uniprot:
            sall_proteins.append((p, sall_uniprot[p]))

    if not sall_proteins:
        return {
            "summary": "SALL proteins not detected in proteomics data -- cannot assess teratogenicity risk",
            "sall_proteins_in_data": [],
            "risk_assessment": "UNKNOWN",
        }

    compounds = [compound_id] if compound_id != "all" else prot.columns.tolist()
    results = []

    for cpd in compounds:
        if cpd not in prot.columns:
            continue

        sall_values = {}  # gene_symbol -> LFC
        for idx_id, gene in sall_proteins:
            val = prot.loc[idx_id, cpd]
            if pd.notna(val):
                sall_values[gene] = float(val)

        # Risk assessment
        sall4_lfc = sall_values.get("SALL4")
        any_sall_degraded = any(v < -0.5 for v in sall_values.values())
        sall4_degraded = sall4_lfc is not None and sall4_lfc < -0.5

        if sall4_degraded:
            risk = "HIGH"
            risk_detail = f"SALL4 degraded (LFC={sall4_lfc:.2f}) -- thalidomide-like teratogenicity risk"
        elif any_sall_degraded:
            risk = "MODERATE"
            degraded_salls = {k: round(v, 3) for k, v in sall_values.items() if v < -0.5}
            risk_detail = f"SALL family member(s) degraded: {degraded_salls} -- potential teratogenicity"
        elif sall4_lfc is not None and sall4_lfc < -0.3:
            risk = "LOW"
            risk_detail = f"SALL4 mildly reduced (LFC={sall4_lfc:.2f}) -- monitor in follow-up"
        else:
            risk = "MINIMAL"
            risk_detail = "No SALL degradation detected"

        results.append({
            "compound": cpd,
            "risk_level": risk,
            "risk_detail": risk_detail,
            "sall_values": sall_values,
        })

    sall_names = [gene for _, gene in sall_proteins]

    if compound_id != "all" and results:
        r = results[0]
        summary = f"SALL4 risk for {compound_id}: {r['risk_level']} -- {r['risk_detail']}"
    else:
        risk_counts = {}
        for r in results:
            risk_counts[r["risk_level"]] = risk_counts.get(r["risk_level"], 0) + 1
        summary = f"SALL4 risk assessment: {len(results)} compounds -- {risk_counts}"

    return {
        "summary": summary,
        "sall_proteins_in_data": sall_names,
        "assessments": results,
    }
