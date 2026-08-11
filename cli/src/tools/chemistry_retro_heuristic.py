"""chemistry.retrosynthesis: heuristic RDKit SMARTS-based disconnection fallback. Split from tools/chemistry.py."""
from tools.chemistry_retro_transforms import RETRO_TRANSFORMS


def retrosynthesis_heuristic(smiles: str, max_steps: int) -> dict:
    """Heuristic retrosynthesis using RDKit SMARTS-based disconnections."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": f"Invalid SMILES: {smiles}", "summary": f"Could not parse SMILES: {smiles}"}

    disconnections = []
    for transform in RETRO_TRANSFORMS:
        pattern = Chem.MolFromSmarts(transform["product_smarts"])
        if pattern is None:
            continue
        matches = mol.GetSubstructMatches(pattern)
        if matches:
            disconnections.append({
                "transform_name": transform["name"],
                "description": transform["description"],
                "n_sites": len(matches),
                "atom_indices": [list(m) for m in matches[:3]],  # cap at 3
                "reagents": transform["reagents"],
                "conditions": transform["conditions"],
                "reaction_class": transform["reaction_class"],
            })

    if not disconnections:
        return {
            "summary": f"[HEURISTIC FALLBACK] Retrosynthesis for {smiles}: no heuristic disconnections found — "
                       "molecule may require specialized chemistry. Configure api.ibm_rxn_key for AI-powered retrosynthesis.",
            "target": smiles,
            "source": "heuristic",
            "n_routes": 0,
            "routes": [],
            "disconnections": [],
        }

    # Build routes: each disconnection is a potential first step
    routes = []
    for i, disc in enumerate(disconnections):
        route_steps = [{
            "step": 1,
            "transform": disc["transform_name"],
            "description": disc["description"],
            "reagents": disc["reagents"],
            "conditions": disc["conditions"],
            "n_disconnection_sites": disc["n_sites"],
        }]
        routes.append({"route_id": i + 1, "strategy": disc["transform_name"], "n_steps": 1, "steps": route_steps, "reaction_class": disc["reaction_class"]})

    # BRICS decomposition for deeper analysis
    brics_fragments = []
    try:
        from rdkit.Chem import BRICS
        brics_fragments = list(BRICS.BRICSDecompose(mol, returnMols=False))[:10]  # cap output
    except Exception:
        pass

    if brics_fragments and len(brics_fragments) > 1:
        brics_steps = [{"step": j + 1, "fragment": frag, "description": f"BRICS fragment {j + 1}"} for j, frag in enumerate(brics_fragments)]
        routes.append({
            "route_id": len(routes) + 1,
            "strategy": "BRICS full decomposition",
            "n_steps": len(brics_fragments),
            "steps": brics_steps,
            "reaction_class": "brics",
        })

    mw = Descriptors.MolWt(mol)
    formula = rdMolDescriptors.CalcMolFormula(mol)

    routes.sort(key=lambda r: r["n_steps"])

    return {
        "summary": f"[HEURISTIC FALLBACK] Retrosynthesis for {formula} ({smiles}): {len(routes)} routes found "
                   f"via SMARTS-based disconnection (not AI-predicted). Configure api.ibm_rxn_key for more accurate routes.",
        "target": smiles,
        "formula": formula,
        "molecular_weight": round(mw, 1),
        "source": "heuristic",
        "n_routes": len(routes),
        "routes": routes,
        "disconnections": disconnections,
        "brics_fragments": brics_fragments,
    }
