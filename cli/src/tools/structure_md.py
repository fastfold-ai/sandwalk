"""structure.md_simulate: molecular dynamics simulation job submission (cloud GPU only).

Split from tools/structure.py.
"""

from pathlib import Path

from tools import registry


@registry.register(
    name="structure.md_simulate",
    description="Submit a molecular dynamics simulation job (OpenMM/GROMACS) to cloud GPU compute",
    category="structure",
    parameters={
        "pdb_path": "Path to input PDB structure",
        "duration_ns": "Simulation duration in nanoseconds (default 10.0)",
        "forcefield": "Force field: amber14 (default), charmm36, opls",
        "temperature_k": "Temperature in Kelvin (default 300.0)",
    },
    usage_guide=(
        "You want to run an MD simulation to study protein dynamics, ligand "
        "stability in a binding pocket, or conformational sampling. This is "
        "always a cloud GPU job — too computationally intensive for local execution."
    ),
)
def md_simulate(pdb_path: str, duration_ns: float = 10.0,
                forcefield: str = "amber14", temperature_k: float = 300.0,
                **kwargs) -> dict:
    """Submit an MD simulation to cloud GPU compute.

    Prepares an OpenMM/GROMACS job configuration and submits via
    ``compute.submit_job``.  Always a cloud job.
    """
    valid_forcefields = ("amber14", "charmm36", "opls")
    if forcefield not in valid_forcefields:
        return {"error": f"Unknown forcefield '{forcefield}'. Choose from: {', '.join(valid_forcefields)}", "summary": f"Unknown forcefield '{forcefield}'. Choose from: {', '.join(valid_forcefields)}"}
    if duration_ns <= 0:
        return {"error": "duration_ns must be positive", "summary": "duration_ns must be positive"}
    if temperature_k <= 0:
        return {"error": "temperature_k must be positive", "summary": "temperature_k must be positive"}
    pdb = Path(pdb_path)
    if not pdb.exists():
        return {"error": f"PDB file not found: {pdb_path}",
                "summary": "MD simulation failed: PDB file not found"}

    # Estimate runtime: ~1 ns/hr on a single A100 for a typical protein
    estimated_hours = duration_ns * 1.0  # rough heuristic
    protein_name = pdb.stem

    config = {
        "pdb_path": str(pdb),
        "duration_ns": duration_ns,
        "forcefield": forcefield,
        "temperature_k": temperature_k,
        "integrator": "LangevinMiddle",
        "timestep_fs": 2.0,
        "solvent": "tip3p",
        "ionic_strength_M": 0.15,
        "reporting_interval_ps": 10.0,
        "platform": "CUDA",
    }

    from tools.compute import submit_job
    job_result = submit_job(
        job_type="molecular_dynamics",
        params={
            "n_samples": 1,
            "config": config,
        },
        dry_run=kwargs.get("dry_run", True),
    )

    if "error" in job_result:
        return {
            "error": job_result["error"],
            "summary": f"MD simulation submission failed: {job_result['error']}",
        }

    return {
        "summary": (
            f"MD simulation submitted: {protein_name} for {duration_ns}ns at "
            f"{temperature_k}K ({forcefield})"
            + (f" (job: {job_result.get('job_id', 'dry-run')})" if not job_result.get("dry_run") else " [DRY RUN]")
        ),
        "config": config,
        "estimated_hours": round(estimated_hours, 1),
        "job": job_result,
    }
