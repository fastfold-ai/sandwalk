"""safety.admet_predict: RDKit-based ADMET property prediction. Split from tools/safety.py."""

from tools import registry


@registry.register(
    name="safety.admet_predict",
    description="Predict ADMET properties for a compound from SMILES using RDKit descriptors and heuristic rules",
    category="safety",
    parameters={
        "smiles": "SMILES string for the compound to profile",
    },
    usage_guide="You need a comprehensive ADMET (absorption, distribution, metabolism, excretion, toxicity) profile for a compound. Use early in lead optimization to flag liabilities before synthesis. Covers Lipinski, Veber, Ghose, lead-likeness, oral absorption, BBB, hERG, CYP, and solubility.",
)
def admet_predict(smiles: str, **kwargs) -> dict:
    """Predict ADMET properties from SMILES using RDKit descriptors and heuristic rules.

    Computes physicochemical properties and applies established medicinal chemistry
    filters (Lipinski Ro5, Veber, Ghose, lead-likeness) plus heuristic predictions
    for oral absorption, BBB penetration, hERG risk, CYP liability, and solubility.
    """
    from tools.chemistry import _extract_smiles
    smiles = _extract_smiles(smiles)

    try:
        from rdkit import Chem
        from rdkit.Chem import Crippen, Descriptors, Lipinski, rdMolDescriptors
    except ImportError:
        return {"error": "RDKit is required for ADMET prediction. Install with: pip install rdkit", "summary": "RDKit is required for ADMET prediction. Install with: pip install rdkit"}
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": f"Invalid SMILES: {smiles}", "summary": f"Could not parse SMILES: {smiles}"}

    # --- Physicochemical descriptors ---
    mw = Descriptors.MolWt(mol)
    logp = Crippen.MolLogP(mol)
    tpsa = Descriptors.TPSA(mol)
    hba = Lipinski.NumHAcceptors(mol)
    hbd = Lipinski.NumHDonors(mol)
    rotatable_bonds = Descriptors.NumRotatableBonds(mol)
    aromatic_rings = Descriptors.NumAromaticRings(mol)
    num_rings = Descriptors.RingCount(mol)
    heavy_atoms = mol.GetNumHeavyAtoms()
    formula = rdMolDescriptors.CalcMolFormula(mol)

    properties = {
        "smiles": smiles,
        "formula": formula,
        "molecular_weight": round(mw, 2),
        "logp": round(logp, 2),
        "tpsa": round(tpsa, 2),
        "hba": hba,
        "hbd": hbd,
        "rotatable_bonds": rotatable_bonds,
        "aromatic_rings": aromatic_rings,
        "num_rings": num_rings,
        "heavy_atoms": heavy_atoms,
    }

    # --- Drug-likeness filters ---
    filters = {}

    # Lipinski Rule of Five
    lipinski_violations = sum([
        mw > 500,
        logp > 5,
        hbd > 5,
        hba > 10,
    ])
    filters["lipinski_ro5"] = {
        "pass": lipinski_violations <= 1,
        "violations": lipinski_violations,
        "details": {
            "MW<=500": mw <= 500,
            "LogP<=5": logp <= 5,
            "HBD<=5": hbd <= 5,
            "HBA<=10": hba <= 10,
        },
    }

    # Veber rule (oral bioavailability)
    veber_pass = tpsa <= 140 and rotatable_bonds <= 10
    filters["veber"] = {
        "pass": veber_pass,
        "details": {
            "TPSA<=140": tpsa <= 140,
            "RotBonds<=10": rotatable_bonds <= 10,
        },
    }

    # Lead-likeness (Teague/Oprea)
    lead_like = mw <= 350 and logp <= 3.5 and rotatable_bonds <= 7
    filters["lead_likeness"] = {
        "pass": lead_like,
        "details": {
            "MW<=350": mw <= 350,
            "LogP<=3.5": logp <= 3.5,
            "RotBonds<=7": rotatable_bonds <= 7,
        },
    }

    # Ghose filter
    ghose_pass = (
        160 <= mw <= 480
        and -0.4 <= logp <= 5.6
        and 40 <= heavy_atoms <= 130  # using heavy atoms as proxy for atom count
        and 20 <= Descriptors.MolMR(mol) <= 130
    )
    filters["ghose"] = {
        "pass": ghose_pass,
        "details": {
            "160<=MW<=480": 160 <= mw <= 480,
            "-0.4<=LogP<=5.6": -0.4 <= logp <= 5.6,
            "20<=MR<=130": 20 <= Descriptors.MolMR(mol) <= 130,
        },
    }

    # --- ADMET predictions (heuristic) ---
    predictions = {}

    # Oral absorption
    oral_absorption = tpsa < 140 and rotatable_bonds <= 10
    oral_score = max(0, 100 - (max(0, tpsa - 60) * 0.8) - (max(0, rotatable_bonds - 5) * 5))
    predictions["oral_absorption"] = {
        "prediction": "likely" if oral_absorption else "poor",
        "score": round(min(100, oral_score), 1),
        "rationale": f"TPSA={tpsa:.0f} ({'<' if tpsa < 140 else '>='} 140), "
                     f"RotBonds={rotatable_bonds} ({'<=' if rotatable_bonds <= 10 else '>'} 10)",
    }

    # BBB penetration
    bbb = tpsa < 90 and mw < 450 and 1 <= logp <= 3
    bbb_score = max(0, 100 - max(0, tpsa - 40) * 1.2 - max(0, mw - 300) * 0.3 - abs(logp - 2) * 15)
    predictions["bbb_penetration"] = {
        "prediction": "likely" if bbb else "unlikely",
        "score": round(min(100, bbb_score), 1),
        "rationale": f"TPSA={tpsa:.0f} ({'<' if tpsa < 90 else '>='} 90), "
                     f"MW={mw:.0f} ({'<' if mw < 450 else '>='} 450), "
                     f"LogP={logp:.1f} ({'in' if 1 <= logp <= 3 else 'outside'} 1-3)",
    }

    # hERG risk (rough heuristic)
    herg_risk = logp > 3.7 and mw > 400
    herg_concern = "elevated" if herg_risk else "low"
    predictions["herg_risk"] = {
        "prediction": herg_concern,
        "flag": herg_risk,
        "rationale": f"LogP={logp:.1f} ({'>' if logp > 3.7 else '<='} 3.7), "
                     f"MW={mw:.0f} ({'>' if mw > 400 else '<='} 400). "
                     f"Lipophilic, large molecules more likely to block hERG channel.",
    }

    # CYP liability
    cyp_risk_factors = 0
    cyp_details = []
    if aromatic_rings >= 3:
        cyp_risk_factors += 1
        cyp_details.append(f"{aromatic_rings} aromatic rings (>=3)")
    if logp > 3:
        cyp_risk_factors += 1
        cyp_details.append(f"LogP={logp:.1f} (>3)")
    if mw > 500:
        cyp_risk_factors += 1
        cyp_details.append(f"MW={mw:.0f} (>500)")

    cyp_level = "high" if cyp_risk_factors >= 2 else "moderate" if cyp_risk_factors == 1 else "low"
    predictions["cyp_liability"] = {
        "prediction": cyp_level,
        "risk_factors": cyp_risk_factors,
        "details": cyp_details if cyp_details else ["No major CYP liability flags"],
    }

    # Solubility class (simplified Yalkowsky-based heuristic: logS ~ 0.5 - 0.01*(MP) - logP)
    # Without melting point, use MW as rough proxy: logS ~ 0.5 - 0.01*MW - logP
    log_s_est = 0.5 - 0.01 * mw - logp
    if log_s_est > -1:
        sol_class = "highly soluble"
    elif log_s_est > -3:
        sol_class = "soluble"
    elif log_s_est > -5:
        sol_class = "moderately soluble"
    elif log_s_est > -7:
        sol_class = "poorly soluble"
    else:
        sol_class = "insoluble"

    predictions["solubility"] = {
        "class": sol_class,
        "estimated_logS": round(log_s_est, 2),
        "rationale": f"Estimated logS={log_s_est:.2f} (Yalkowsky-type heuristic from MW and LogP)",
    }

    # --- Overall ADMET verdict ---
    flags = []
    if not filters["lipinski_ro5"]["pass"]:
        flags.append(f"Lipinski: {lipinski_violations} violations")
    if not veber_pass:
        flags.append("Fails Veber (oral bioavailability concern)")
    if herg_risk:
        flags.append("Elevated hERG risk")
    if cyp_level == "high":
        flags.append("High CYP liability")
    if sol_class in ("poorly soluble", "insoluble"):
        flags.append(f"Solubility: {sol_class}")

    if not flags:
        verdict = "FAVORABLE"
    elif len(flags) <= 2:
        verdict = "ACCEPTABLE"
    else:
        verdict = "UNFAVORABLE"

    summary_parts = [
        f"ADMET profile for {formula} (MW={mw:.0f}, LogP={logp:.1f}): {verdict}",
        f"Lipinski: {'PASS' if filters['lipinski_ro5']['pass'] else 'FAIL'} ({lipinski_violations} violations)",
        f"Oral absorption: {predictions['oral_absorption']['prediction']} (score {predictions['oral_absorption']['score']})",
        f"BBB: {predictions['bbb_penetration']['prediction']} (score {predictions['bbb_penetration']['score']})",
        f"hERG: {predictions['herg_risk']['prediction']}, CYP: {predictions['cyp_liability']['prediction']}",
        f"Solubility: {predictions['solubility']['class']} (logS~{log_s_est:.1f})",
    ]
    if flags:
        summary_parts.append(f"Flags: {'; '.join(flags)}")

    return {
        "summary": "\n".join(summary_parts),
        "verdict": verdict,
        "properties": properties,
        "filters": filters,
        "predictions": predictions,
        "flags": flags,
    }
