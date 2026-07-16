"""parity: chemistry.sa_score synthetic accessibility heuristic.

Split from tools/parity.py.
"""

from __future__ import annotations

from tools import registry


def _count_aromatic_rings(mol) -> int:
    try:
        return sum(1 for ring in mol.GetRingInfo().AtomRings() if any(mol.GetAtomWithIdx(i).GetIsAromatic() for i in ring))
    except Exception:
        return 0


@registry.register(
    name="chemistry.sa_score",
    description="Estimate synthetic accessibility score (1 easy – 10 hard)",
    category="chemistry",
    parameters={"smiles": "Input SMILES"},
    usage_guide="Use during hit triage to reject compounds likely to be difficult to synthesize.",
)
def sa_score(smiles: str, **kwargs) -> dict:
    """Heuristic synthetic accessibility estimate based on molecular complexity."""
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, Lipinski
    except Exception:
        return {
            "summary": "RDKit is required for chemistry.sa_score.",
            "error": "missing_dependency",
        }

    smi = (smiles or "").strip()
    if not smi:
        return {"summary": "smiles is required.", "error": "missing_smiles"}

    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return {"summary": f"Invalid SMILES: {smi}", "error": "invalid_smiles"}

    heavy = Descriptors.HeavyAtomCount(mol)
    rings = Lipinski.RingCount(mol)
    aromatic_rings = _count_aromatic_rings(mol)
    sp3 = Lipinski.FractionCSP3(mol)
    rot_bonds = Lipinski.NumRotatableBonds(mol)
    stereo = len(Chem.FindMolChiralCenters(mol, includeUnassigned=True))

    # Lightweight complexity model mapped into [1,10].
    complexity = 0.0
    complexity += min(heavy / 20.0, 2.5)
    complexity += min(rings * 0.35, 2.0)
    complexity += min(aromatic_rings * 0.25, 1.5)
    complexity += min(rot_bonds * 0.12, 1.2)
    complexity += min(stereo * 0.3, 1.8)
    complexity += max(0.0, (0.4 - float(sp3)) * 2.0)

    score = max(1.0, min(10.0, 1.5 + complexity))
    band = "easy" if score <= 3.5 else "moderate" if score <= 6.0 else "hard"

    return {
        "summary": f"Estimated synthetic accessibility score: {score:.2f}/10 ({band}).",
        "smiles": smi,
        "sa_score": round(score, 2),
        "difficulty": band,
        "features": {
            "heavy_atoms": int(heavy),
            "ring_count": int(rings),
            "aromatic_rings": int(aromatic_rings),
            "fraction_csp3": round(float(sp3), 3),
            "rotatable_bonds": int(rot_bonds),
            "stereocenters": int(stereo),
        },
        "note": "Heuristic estimate for prioritization; not a replacement for route planning.",
    }
