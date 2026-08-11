"""structure.alphafold_fetch / compound_3d / _resolve_pdb: structure fetch and 3D generation.

Split from tools/structure.py. Reads ``CONFIG_DIR``/``request`` indirectly via the
``tools.structure`` hub module so that ``patch("tools.structure.CONFIG_DIR")`` /
``patch("tools.structure.request")`` in tests continue to work regardless of which
submodule performs the call.
"""

from pathlib import Path

from tools import registry
from tools import structure as _structure


@registry.register(
    name="structure.alphafold_fetch",
    description="Download AlphaFold predicted structure for a protein",
    category="structure",
    parameters={"uniprot_id": "UniProt ID"},
    usage_guide="You need a 3D structure for a target protein and no experimental structure is available. Fetches AlphaFold prediction. Use before ternary_predict or structure analysis.",
)
def alphafold_fetch(uniprot_id: str, **kwargs) -> dict:
    """Download AlphaFold structure for a protein."""
    cache_dir = _structure.CONFIG_DIR / "cache" / "alphafold"
    cache_dir.mkdir(parents=True, exist_ok=True)

    output_path = cache_dir / f"AF-{uniprot_id}-F1-model_v4.pdb"

    if output_path.exists():
        return {
            "summary": f"AlphaFold structure for {uniprot_id} (cached)",
            "path": str(output_path),
            "cached": True,
        }

    url = f"https://alphafold.ebi.ac.uk/files/AF-{uniprot_id}-F1-model_v4.pdb"
    response, error = _structure.request(
        "GET",
        url,
        timeout=30,
        retries=2,
        raise_for_status=False,
    )
    if error:
        return {"error": f"Failed to fetch AlphaFold structure: {error}", "summary": f"Failed to fetch AlphaFold structure: {error}"}
    if response.status_code == 200 and response.text.startswith("HEADER"):
        output_path.write_text(response.text)
        return {
            "summary": f"Downloaded AlphaFold structure for {uniprot_id}",
            "path": str(output_path),
            "cached": False,
        }
    else:
        return {"error": f"AlphaFold structure not available for {uniprot_id} (HTTP {response.status_code})", "summary": f"AlphaFold structure not available for {uniprot_id} (HTTP {response.status_code})"}


@registry.register(
    name="structure.compound_3d",
    description="Generate 3D conformer from SMILES and save as SDF",
    category="structure",
    parameters={"smiles": "SMILES string", "output_path": "Output SDF path"},
    usage_guide="You need a 3D structure for a small molecule compound. Use before docking or ternary complex prediction when you only have a SMILES string.",
)
def compound_3d(smiles: str, output_path: str = None, **kwargs) -> dict:
    """Generate 3D conformer for a compound."""
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": f"Invalid SMILES: {smiles}", "summary": f"Invalid SMILES: {smiles}"}
    mol = Chem.AddHs(mol)
    result = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    if result != 0:
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3(), randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)

    if output_path:
        writer = Chem.SDWriter(output_path)
        writer.write(mol)
        writer.close()

    return {
        "summary": f"3D conformer generated ({Descriptors.MolWt(mol):.1f} Da, {mol.GetNumAtoms()} atoms)",
        "smiles": smiles,
        "n_atoms": mol.GetNumAtoms(),
        "output_path": output_path,
    }


def _resolve_pdb(target_pdb: str) -> dict:
    """Resolve a target identifier to a local PDB file path.

    Accepts either a local file path or a UniProt ID.  When a UniProt ID is
    given the AlphaFold structure is fetched first via *alphafold_fetch*.

    Returns ``{"path": str}`` on success or ``{"error": str}`` on failure.
    """
    p = Path(target_pdb)
    if p.exists():
        return {"path": str(p)}

    # Treat as UniProt ID — try AlphaFold download
    result = _structure.alphafold_fetch(target_pdb)
    if "error" in result:
        return {"error": f"Could not resolve target '{target_pdb}': {result['error']}", "summary": f"Could not resolve target '{target_pdb}': {result['error']}"}
    return {"path": result["path"]}
