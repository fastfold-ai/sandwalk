"""
Design tools: compound modification suggestions, med-chem optimization.

Provides AI-guided medicinal chemistry recommendations using RDKit-based
property calculations, bioisosteric replacement rules, and Lipinski/Veber
scoring.
"""

from tools import registry
from tools.design_scoring import (
    _compute_properties,
    _lipinski_violations,
    _score_for_objective,
    _veber_violations,
)
from tools.design_transforms import _apply_medchem_transforms, _apply_simple_additions

__all__ = [
    "suggest_modifications",
    "_compute_properties",
    "_lipinski_violations",
    "_veber_violations",
    "_score_for_objective",
]


@registry.register(
    name="design.suggest_modifications",
    description="Suggest medicinal chemistry modifications to improve a compound's properties",
    category="design",
    parameters={
        "smiles": "Input compound SMILES string",
        "objective": "Optimization goal: potency, selectivity, admet, solubility, metabolic_stability (default: potency)",
        "n_suggestions": "Number of suggestions to return (default 5)",
    },
    usage_guide=(
        "You have a hit or lead compound and want to generate ideas for "
        "structural modifications to improve potency, selectivity, ADMET, "
        "solubility, or metabolic stability. Returns modified SMILES with "
        "property comparisons and medicinal chemistry rationale."
    ),
)
def suggest_modifications(smiles: str, objective: str = "potency",
                          n_suggestions: int = 5, **kwargs) -> dict:
    """Suggest medicinal chemistry modifications for a compound.

    Applies bioisosteric replacements and common med-chem transforms using
    RDKit reaction SMARTS, then scores each modification against the
    specified objective.
    """
    try:
        from rdkit import Chem
    except ImportError:
        return {"error": "RDKit is required for compound modification suggestions (pip install rdkit)", "summary": "RDKit is required for compound modification suggestions (pip install rdkit)"}
    valid_objectives = ("potency", "selectivity", "admet", "solubility", "metabolic_stability")
    if objective not in valid_objectives:
        return {"error": f"Unknown objective '{objective}'. Choose from: {', '.join(valid_objectives)}", "summary": f"Unknown objective '{objective}'. Choose from: {', '.join(valid_objectives)}"}
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": f"Invalid SMILES: {smiles}", "summary": f"Could not parse SMILES: {smiles}"}

    parent_props = _compute_properties(mol)
    parent_violations = _lipinski_violations(parent_props)
    canonical = Chem.MolToSmiles(mol)

    seen_smiles = {canonical}
    suggestions = _apply_medchem_transforms(mol, parent_props, objective, seen_smiles)

    # Also add simple functional group additions if we have few suggestions
    suggestions += _apply_simple_additions(mol, parent_props, objective, seen_smiles, n_suggestions)

    # Sort by score descending, take top n
    suggestions.sort(key=lambda s: s["score"], reverse=True)
    top = suggestions[:n_suggestions]

    if not top:
        return {
            "summary": f"No modifications found for {smiles} (no applicable transforms matched)",
            "parent_smiles": canonical,
            "parent_properties": parent_props,
            "suggestions": [],
        }

    # Build summary
    best = top[0]
    logp_delta = best["property_deltas"]["logp"]
    delta_str = f"LogP {logp_delta:+.2f}" if logp_delta != 0 else "similar LogP"

    return {
        "summary": (
            f"{len(top)} modification(s) suggested for {canonical[:40]} "
            f"(objective={objective}): top suggestion {best['transform']} ({delta_str})"
        ),
        "parent_smiles": canonical,
        "parent_properties": parent_props,
        "parent_lipinski_violations": parent_violations,
        "objective": objective,
        "suggestions": top,
    }
