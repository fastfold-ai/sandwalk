"""structure.fep: free energy perturbation job submission (cloud GPU only).

Split from tools/structure.py.
"""

from pathlib import Path

from tools import registry
from tools.structure_fetch import _resolve_pdb


@registry.register(
    name="structure.fep",
    description="Submit a free energy perturbation (FEP) calculation for relative binding free energy between two ligands",
    category="structure",
    parameters={
        "smiles_a": "SMILES for ligand A",
        "smiles_b": "SMILES for ligand B",
        "target_pdb": "Path to target protein PDB or UniProt ID",
        "method": "FEP method: openmm (default), gromacs",
    },
    usage_guide=(
        "You want to predict the relative binding free energy difference "
        "between two similar ligands to a target. Use for lead optimization "
        "when you need to rank-order compound modifications by binding affinity. "
        "Always a cloud GPU job."
    ),
)
def fep(smiles_a: str, smiles_b: str, target_pdb: str,
        method: str = "openmm", **kwargs) -> dict:
    """Submit an FEP calculation for relative binding free energy.

    Prepares the ligand pair and target, then submits to cloud compute.
    """
    valid_methods = ("openmm", "gromacs")
    if method not in valid_methods:
        return {"error": f"Unknown FEP method '{method}'. Choose from: {', '.join(valid_methods)}", "summary": f"Unknown FEP method '{method}'. Choose from: {', '.join(valid_methods)}"}
    # Validate SMILES
    try:
        from rdkit import Chem
    except ImportError:
        return {"error": "RDKit is required for FEP ligand validation (pip install rdkit)", "summary": "RDKit is required for FEP ligand validation (pip install rdkit)"}
    mol_a = Chem.MolFromSmiles(smiles_a)
    mol_b = Chem.MolFromSmiles(smiles_b)
    if mol_a is None:
        return {"error": f"Invalid SMILES for ligand A: {smiles_a}", "summary": f"Invalid SMILES for ligand A: {smiles_a}"}
    if mol_b is None:
        return {"error": f"Invalid SMILES for ligand B: {smiles_b}", "summary": f"Invalid SMILES for ligand B: {smiles_b}"}
    # Resolve target
    target = _resolve_pdb(target_pdb)
    if "error" in target:
        return {"error": target["error"], "summary": f"FEP failed: {target['error']}"}
    pdb_path = target["path"]

    # Estimate runtime: ~4-8 hours per ligand pair on A100
    estimated_hours = 6.0

    config = {
        "smiles_a": smiles_a,
        "smiles_b": smiles_b,
        "target_pdb": pdb_path,
        "method": method,
        "n_lambda_windows": 12,
        "simulation_time_per_window_ns": 5.0,
        "temperature_k": 300.0,
        "platform": "CUDA",
    }

    from tools.compute import submit_job
    job_result = submit_job(
        job_type="molecular_dynamics",
        params={
            "n_samples": 1,
            "fep_config": config,
        },
        dry_run=kwargs.get("dry_run", True),
    )

    if "error" in job_result:
        return {
            "error": job_result["error"],
            "summary": f"FEP submission failed: {job_result['error']}",
        }

    target_name = Path(pdb_path).stem

    return {
        "summary": (
            f"FEP calculation submitted: {smiles_a[:30]} -> {smiles_b[:30]} "
            f"in {target_name} ({method})"
            + (f" (job: {job_result.get('job_id', 'dry-run')})" if not job_result.get("dry_run") else " [DRY RUN]")
        ),
        "config": config,
        "estimated_hours": estimated_hours,
        "transformation": {"ligand_a": smiles_a, "ligand_b": smiles_b},
        "job": job_result,
    }
