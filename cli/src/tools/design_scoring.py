"""Property computation and objective scoring for design.suggest_modifications."""


def _compute_properties(mol) -> dict:
    """Compute drug-relevant molecular properties."""
    from rdkit.Chem import Descriptors, rdMolDescriptors

    return {
        "mw": round(Descriptors.MolWt(mol), 1),
        "logp": round(Descriptors.MolLogP(mol), 2),
        "hbd": Descriptors.NumHDonors(mol),
        "hba": Descriptors.NumHAcceptors(mol),
        "tpsa": round(Descriptors.TPSA(mol), 1),
        "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
        "rings": Descriptors.RingCount(mol),
        "aromatic_rings": Descriptors.NumAromaticRings(mol),
        "fsp3": round(rdMolDescriptors.CalcFractionCSP3(mol), 3),
        "heavy_atoms": mol.GetNumHeavyAtoms(),
    }


def _lipinski_violations(props: dict) -> int:
    """Count Lipinski Rule-of-5 violations."""
    return sum([
        props["mw"] > 500,
        props["logp"] > 5,
        props["hbd"] > 5,
        props["hba"] > 10,
    ])


def _veber_violations(props: dict) -> int:
    """Count Veber oral bioavailability rule violations."""
    return sum([
        props["tpsa"] > 140,
        props["rotatable_bonds"] > 10,
    ])


def _score_for_objective(parent_props: dict, child_props: dict,
                         objective: str) -> float:
    """Score a modification relative to the parent, for a given objective.

    Returns a float where higher is better (range roughly -1 to +1).
    """
    if objective == "potency":
        # Favour: lower MW, moderate LogP (2-4), more H-bond interactions
        logp_score = 1.0 - abs(child_props["logp"] - 3.0) / 5.0
        mw_score = (parent_props["mw"] - child_props["mw"]) / 100.0
        return round(logp_score * 0.5 + mw_score * 0.3 + 0.2, 3)

    elif objective == "selectivity":
        # Favour: more specific interactions (more HBD/HBA), higher TPSA
        hb_delta = (child_props["hbd"] + child_props["hba"]) - (parent_props["hbd"] + parent_props["hba"])
        tpsa_delta = (child_props["tpsa"] - parent_props["tpsa"]) / 50.0
        return round(hb_delta * 0.3 + tpsa_delta * 0.4 + 0.3, 3)

    elif objective == "admet":
        # Favour: fewer Lipinski/Veber violations, moderate LogP
        lip = _lipinski_violations(child_props)
        veb = _veber_violations(child_props)
        penalty = lip * 0.25 + veb * 0.25
        logp_bonus = 1.0 - abs(child_props["logp"] - 2.5) / 5.0
        return round(max(0, 1.0 - penalty) * 0.6 + logp_bonus * 0.4, 3)

    elif objective == "solubility":
        # Favour: lower LogP, higher TPSA, higher Fsp3
        logp_score = max(0, (parent_props["logp"] - child_props["logp"]) / 3.0)
        tpsa_score = max(0, (child_props["tpsa"] - parent_props["tpsa"]) / 40.0)
        fsp3_score = max(0, (child_props["fsp3"] - parent_props["fsp3"]))
        return round(logp_score * 0.4 + tpsa_score * 0.3 + fsp3_score * 0.3, 3)

    elif objective == "metabolic_stability":
        # Favour: fewer metabolic soft spots (reduce ArOH, add F-blocks)
        logp_score = 1.0 - abs(child_props["logp"] - 2.0) / 5.0
        mw_penalty = max(0, (child_props["mw"] - 500) / 200.0)
        rotbond_penalty = max(0, (child_props["rotatable_bonds"] - 7) / 5.0)
        return round(logp_score * 0.4 - mw_penalty * 0.3 - rotbond_penalty * 0.3, 3)

    # Default: balanced score
    return 0.5


def _property_deltas(parent_props: dict, child_props: dict) -> dict:
    """Property deltas shared by all modification-suggestion branches."""
    return {
        "mw": round(child_props["mw"] - parent_props["mw"], 1),
        "logp": round(child_props["logp"] - parent_props["logp"], 2),
        "hbd": child_props["hbd"] - parent_props["hbd"],
        "hba": child_props["hba"] - parent_props["hba"],
        "tpsa": round(child_props["tpsa"] - parent_props["tpsa"], 1),
    }
