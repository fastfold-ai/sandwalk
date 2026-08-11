"""chemistry.scaffold_hop: bioisostere and scaffold-replacement suggestions. Split from tools/chemistry.py."""
from tools import registry
from tools import chemistry as _chemistry
from tools.chemistry_bioisosteres import detect_functional_groups, suggest_scaffold_replacements


@registry.register(
    name="chemistry.scaffold_hop",
    description="Suggest scaffold replacements and bioisosteres for a compound",
    category="chemistry",
    parameters={
        "smiles": "SMILES string for the input compound",
    },
    usage_guide="You want to explore alternative scaffolds for a hit compound — either to improve properties, escape a patent, or find novel chemical matter. Generates bioisosteric replacements for functional groups and suggests scaffold hops based on the Murcko framework.",
)
def scaffold_hop(smiles: str, **kwargs) -> dict:
    """Suggest scaffold replacements and bioisosteric substitutions.

    Extracts the Murcko scaffold, identifies key functional groups, and
    suggests common bioisosteric replacements with rationale.
    """
    smiles = _chemistry._extract_smiles(smiles)
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, rdMolDescriptors
        from rdkit.Chem.Scaffolds import MurckoScaffold
    except ImportError:
        return {"error": "RDKit is required for scaffold hopping. Install with: pip install rdkit", "summary": "RDKit is required for scaffold hopping. Install with: pip install rdkit"}
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": f"Invalid SMILES: {smiles}", "summary": f"Could not parse SMILES: {smiles}"}

    try:
        scaffold_mol = MurckoScaffold.GetScaffoldForMol(mol)
        scaffold_smi = Chem.MolToSmiles(scaffold_mol)
        generic_scaffold = MurckoScaffold.MakeScaffoldGeneric(scaffold_mol)
        generic_smi = Chem.MolToSmiles(generic_scaffold)
    except Exception:
        scaffold_smi, generic_smi = "N/A", "N/A"

    detected_groups, all_bioisosteres = detect_functional_groups(mol)
    scaffold_replacements = suggest_scaffold_replacements(scaffold_smi)

    mw = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    tpsa = Descriptors.TPSA(mol)
    fsp3 = rdMolDescriptors.CalcFractionCSP3(mol)

    property_context = {
        "molecular_weight": round(mw, 1),
        "logp": round(logp, 2),
        "tpsa": round(tpsa, 1),
        "fsp3": round(fsp3, 3),
        "suggestions_for_improvement": [],
    }
    if fsp3 < 0.25:
        property_context["suggestions_for_improvement"].append(
            f"Low Fsp3 ({fsp3:.2f}) — consider sp3-rich scaffold hops (phenyl->cyclohexyl) to improve solubility"
        )
    if logp > 4:
        property_context["suggestions_for_improvement"].append(f"High LogP ({logp:.1f}) — add heteroatoms or polar groups to improve solubility")
    if tpsa < 40:
        property_context["suggestions_for_improvement"].append(f"Low TPSA ({tpsa:.0f}) — may have poor solubility; consider adding H-bond acceptors")

    summary_lines = [
        f"Scaffold analysis for {smiles}",
        f"Murcko scaffold: {scaffold_smi}",
        f"Generic framework: {generic_smi}",
        f"Detected functional groups: {', '.join(g['group'] for g in detected_groups) if detected_groups else 'none identified'}",
        f"Bioisostere suggestions: {len(all_bioisosteres)}",
        f"Scaffold hop options: {len(scaffold_replacements)}",
    ]

    return {
        "summary": "\n".join(summary_lines),
        "input_smiles": smiles,
        "murcko_scaffold": scaffold_smi,
        "generic_framework": generic_smi,
        "detected_functional_groups": detected_groups,
        "bioisostere_suggestions": all_bioisosteres,
        "scaffold_replacements": scaffold_replacements,
        "property_context": property_context,
    }
