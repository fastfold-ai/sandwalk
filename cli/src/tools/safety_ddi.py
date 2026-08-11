"""safety.ddi_predict: RDKit CYP-motif-based drug-drug interaction prediction.

Split from tools/safety.py.
"""

from tools import registry


@registry.register(
    name="safety.ddi_predict",
    description="Predict drug-drug interaction potential based on CYP metabolism profile and molecular features",
    category="safety",
    parameters={
        "smiles": "SMILES string for the primary compound",
        "comedication_smiles": "SMILES string for a co-administered drug (optional)",
    },
    usage_guide="You need to assess drug-drug interaction risk for a compound, especially CYP-mediated interactions. Use when evaluating combination therapies or compounds likely to be co-prescribed. Identifies CYP inhibition/induction risk from structural features.",
)
def ddi_predict(smiles: str, comedication_smiles: str = None, **kwargs) -> dict:
    """Predict drug-drug interaction potential based on CYP metabolism profile.

    Uses structural features to estimate CYP inhibition risk for major isoforms
    (3A4, 2D6, 2C9, 2C19, 1A2). Optionally compares with a co-medication.
    """
    from tools.chemistry import _extract_smiles
    smiles = _extract_smiles(smiles)

    try:
        from rdkit import Chem
        from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors
    except ImportError:
        return {"error": "RDKit is required for DDI prediction. Install with: pip install rdkit", "summary": "RDKit is required for DDI prediction. Install with: pip install rdkit"}
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": f"Invalid SMILES: {smiles}", "summary": f"Could not parse SMILES: {smiles}"}

    mw = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    _tpsa = Descriptors.TPSA(mol)
    aromatic_rings = Descriptors.NumAromaticRings(mol)
    num_rings = Descriptors.RingCount(mol)
    _hba = Descriptors.NumHAcceptors(mol)

    # --- Detect structural motifs associated with CYP inhibition ---
    motif_flags = {}

    # Nitrogen heterocycles (CYP3A4 inhibition)
    n_heterocycle_pattern = Chem.MolFromSmarts("[nR]")  # ring nitrogen
    n_heterocycles = len(mol.GetSubstructMatches(n_heterocycle_pattern)) if n_heterocycle_pattern else 0
    motif_flags["nitrogen_heterocycles"] = n_heterocycles

    # Imidazole motif (strong CYP inhibition — azole antifungals)
    # Multiple SMARTS to catch both NH and N-substituted forms
    imidazole_patterns = [
        Chem.MolFromSmarts("c1cnc[nH]1"),   # unsubstituted
        Chem.MolFromSmarts("c1nccn1"),       # N-substituted imidazole
        Chem.MolFromSmarts("c1cncn1"),       # alternative numbering
    ]
    has_imidazole = any(
        pat is not None and bool(mol.GetSubstructMatches(pat))
        for pat in imidazole_patterns
    )

    # Triazole motif
    triazole_1 = Chem.MolFromSmarts("c1nncn1")
    triazole_2 = Chem.MolFromSmarts("c1nnn[nH]1")
    has_triazole = (
        (bool(mol.GetSubstructMatches(triazole_1)) if triazole_1 else False)
        or (bool(mol.GetSubstructMatches(triazole_2)) if triazole_2 else False)
    )
    motif_flags["has_imidazole"] = has_imidazole
    motif_flags["has_triazole"] = has_triazole
    motif_flags["has_azole"] = has_imidazole or has_triazole

    # Furanyl groups (mechanism-based CYP inhibition)
    furan = Chem.MolFromSmarts("c1ccoc1")
    has_furan = bool(mol.GetSubstructMatches(furan)) if furan else False
    motif_flags["has_furan"] = has_furan

    # Amine groups (CYP2D6 substrates/inhibitors)
    basic_amine = Chem.MolFromSmarts("[NX3;!$(NC=O);!$(NS=O)]")
    n_basic_amines = len(mol.GetSubstructMatches(basic_amine)) if basic_amine else 0
    motif_flags["basic_amines"] = n_basic_amines

    # --- CYP isoform risk assessment ---
    cyp_profile = {}

    # CYP3A4 — the major drug-metabolizing enzyme
    cyp3a4_score = 0
    cyp3a4_reasons = []
    if has_imidazole or has_triazole:
        cyp3a4_score += 3
        cyp3a4_reasons.append("Azole motif (strong CYP3A4 inhibition)")
    if n_heterocycles >= 2:
        cyp3a4_score += 1
        cyp3a4_reasons.append(f"{n_heterocycles} nitrogen heterocycles")
    if mw > 400 and logp > 3:
        cyp3a4_score += 1
        cyp3a4_reasons.append(f"Large lipophilic molecule (MW={mw:.0f}, LogP={logp:.1f})")
    cyp_profile["CYP3A4"] = {
        "inhibition_risk": "high" if cyp3a4_score >= 3 else "moderate" if cyp3a4_score >= 1 else "low",
        "score": cyp3a4_score,
        "reasons": cyp3a4_reasons if cyp3a4_reasons else ["No major CYP3A4 inhibition flags"],
    }

    # CYP2D6
    cyp2d6_score = 0
    cyp2d6_reasons = []
    if n_basic_amines >= 1:
        cyp2d6_score += 1
        cyp2d6_reasons.append(f"{n_basic_amines} basic amine(s) — CYP2D6 substrate/inhibitor feature")
    if aromatic_rings >= 2 and n_basic_amines >= 1:
        cyp2d6_score += 1
        cyp2d6_reasons.append("Lipophilic amine — classic CYP2D6 inhibitor pharmacophore")
    cyp_profile["CYP2D6"] = {
        "inhibition_risk": "high" if cyp2d6_score >= 2 else "moderate" if cyp2d6_score >= 1 else "low",
        "score": cyp2d6_score,
        "reasons": cyp2d6_reasons if cyp2d6_reasons else ["No major CYP2D6 inhibition flags"],
    }

    # CYP2C9
    cyp2c9_score = 0
    cyp2c9_reasons = []
    if logp > 3 and aromatic_rings >= 2:
        cyp2c9_score += 1
        cyp2c9_reasons.append("Lipophilic aromatic compound")
    # Acidic groups — CYP2C9 substrates tend to be weak acids
    carboxylic = Chem.MolFromSmarts("[CX3](=O)[OX2H1]")
    has_acid = bool(mol.GetSubstructMatches(carboxylic)) if carboxylic else False
    if has_acid:
        cyp2c9_score += 1
        cyp2c9_reasons.append("Carboxylic acid group — CYP2C9 substrate feature")
    cyp_profile["CYP2C9"] = {
        "inhibition_risk": "moderate" if cyp2c9_score >= 1 else "low",
        "score": cyp2c9_score,
        "reasons": cyp2c9_reasons if cyp2c9_reasons else ["No major CYP2C9 inhibition flags"],
    }

    # CYP2C19
    cyp2c19_score = 0
    cyp2c19_reasons = []
    if has_imidazole:
        cyp2c19_score += 2
        cyp2c19_reasons.append("Imidazole motif (CYP2C19 inhibitor feature)")
    if n_heterocycles >= 2 and mw < 500:
        cyp2c19_score += 1
        cyp2c19_reasons.append("Multiple nitrogen heterocycles")
    cyp_profile["CYP2C19"] = {
        "inhibition_risk": "high" if cyp2c19_score >= 2 else "moderate" if cyp2c19_score >= 1 else "low",
        "score": cyp2c19_score,
        "reasons": cyp2c19_reasons if cyp2c19_reasons else ["No major CYP2C19 inhibition flags"],
    }

    # CYP1A2
    cyp1a2_score = 0
    cyp1a2_reasons = []
    if aromatic_rings >= 3:
        cyp1a2_score += 1
        cyp1a2_reasons.append(f"{aromatic_rings} aromatic rings — planar aromatic CYP1A2 substrate")
    # Fused ring systems
    if num_rings >= 3 and aromatic_rings >= 2:
        cyp1a2_score += 1
        cyp1a2_reasons.append("Polycyclic aromatic system")
    cyp_profile["CYP1A2"] = {
        "inhibition_risk": "moderate" if cyp1a2_score >= 1 else "low",
        "score": cyp1a2_score,
        "reasons": cyp1a2_reasons if cyp1a2_reasons else ["No major CYP1A2 inhibition flags"],
    }

    # --- Mechanism-based inhibition (MBI) risk ---
    mbi_risk = False
    mbi_reasons = []
    if has_furan:
        mbi_risk = True
        mbi_reasons.append("Furan ring — known MBI risk (bioactivated to reactive epoxide)")
    # Terminal alkyne
    alkyne = Chem.MolFromSmarts("[CX2]#[CX2H1]")
    if alkyne and mol.GetSubstructMatches(alkyne):
        mbi_risk = True
        mbi_reasons.append("Terminal alkyne — potential MBI via ketene intermediate")
    # Methylenedioxy
    mdp = Chem.MolFromSmarts("c1cc2OCOc2cc1")
    if mdp and mol.GetSubstructMatches(mdp):
        mbi_risk = True
        mbi_reasons.append("Methylenedioxy group — known CYP MBI risk (carbene formation)")

    # --- Overall DDI risk ---
    high_risk_cyps = [k for k, v in cyp_profile.items() if v["inhibition_risk"] == "high"]
    moderate_risk_cyps = [k for k, v in cyp_profile.items() if v["inhibition_risk"] == "moderate"]

    if high_risk_cyps or mbi_risk:
        overall_risk = "HIGH"
    elif len(moderate_risk_cyps) >= 2:
        overall_risk = "MODERATE"
    elif moderate_risk_cyps:
        overall_risk = "LOW-MODERATE"
    else:
        overall_risk = "LOW"

    # --- Co-medication analysis ---
    comedication_analysis = None
    if comedication_smiles:
        comol = Chem.MolFromSmiles(comedication_smiles)
        if comol is not None:
            co_mw = Descriptors.MolWt(comol)
            co_logp = Crippen.MolLogP(comol)
            _co_aromatic = Descriptors.NumAromaticRings(comol)

            # Check if comedication shares metabolic pathway features
            co_n_het = Chem.MolFromSmarts("[nR]")
            co_n_heterocycles = len(comol.GetSubstructMatches(co_n_het)) if co_n_het else 0
            co_basic_amine = Chem.MolFromSmarts("[NX3;!$(NC=O);!$(NS=O)]")
            co_amines = len(comol.GetSubstructMatches(co_basic_amine)) if co_basic_amine else 0

            shared_pathways = []
            if (n_heterocycles >= 2 or has_imidazole) and co_n_heterocycles >= 2:
                shared_pathways.append("CYP3A4 (both contain N-heterocycles)")
            if n_basic_amines >= 1 and co_amines >= 1:
                shared_pathways.append("CYP2D6 (both contain basic amines)")
            if logp > 3 and co_logp > 3:
                shared_pathways.append("General CYP competition (both lipophilic)")

            interaction_risk = "high" if shared_pathways else "low"

            comedication_analysis = {
                "comedication_smiles": comedication_smiles,
                "comedication_mw": round(co_mw, 1),
                "comedication_logp": round(co_logp, 2),
                "shared_metabolic_pathways": shared_pathways,
                "interaction_risk": interaction_risk,
                "recommendation": (
                    f"Monitor for interactions via {', '.join(shared_pathways)}"
                    if shared_pathways
                    else "Low structural overlap in CYP-relevant features"
                ),
            }
        else:
            comedication_analysis = {"error": f"Invalid co-medication SMILES: {comedication_smiles}"}

    # --- Summary ---
    summary_lines = [
        f"DDI risk assessment: {overall_risk}",
    ]
    if high_risk_cyps:
        summary_lines.append(f"High CYP inhibition risk: {', '.join(high_risk_cyps)}")
    if moderate_risk_cyps:
        summary_lines.append(f"Moderate CYP inhibition risk: {', '.join(moderate_risk_cyps)}")
    if mbi_risk:
        summary_lines.append(f"Mechanism-based inhibition risk: {'; '.join(mbi_reasons)}")
    if motif_flags["has_azole"]:
        summary_lines.append("Contains azole motif — strong CYP inhibitor pharmacophore")
    if comedication_analysis and isinstance(comedication_analysis, dict) and "shared_metabolic_pathways" in comedication_analysis:
        if comedication_analysis["shared_metabolic_pathways"]:
            summary_lines.append(f"Co-medication interaction via: {', '.join(comedication_analysis['shared_metabolic_pathways'])}")
        else:
            summary_lines.append("Low metabolic pathway overlap with co-medication")

    result = {
        "summary": "\n".join(summary_lines),
        "overall_risk": overall_risk,
        "cyp_profile": cyp_profile,
        "motif_flags": motif_flags,
        "mechanism_based_inhibition": {
            "risk": mbi_risk,
            "reasons": mbi_reasons if mbi_reasons else ["No MBI structural alerts"],
        },
    }

    if comedication_analysis:
        result["comedication_analysis"] = comedication_analysis

    return result
