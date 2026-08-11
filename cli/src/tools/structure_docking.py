"""structure.dock: molecular docking (Vina/DiffDock/gnina), local or cloud.

Split from tools/structure.py. Reads ``subprocess`` indirectly via the ``tools.structure``
hub module so that ``patch("tools.structure.subprocess")`` in tests continues to work
regardless of which submodule performs the call.
"""

from pathlib import Path

from tools import registry
from tools import structure as _structure
from tools.structure_fetch import _resolve_pdb


def _prepare_ligand_pdbqt(smiles: str, work_dir: Path) -> dict:
    """Generate a 3D conformer from SMILES and convert to PDBQT for Vina.

    Returns ``{"path": str, "mol": rdkit.Mol}`` on success,
    ``{"error": str}`` on failure.
    """
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ImportError:
        return {"error": "RDKit is required for ligand preparation (pip install rdkit)", "summary": "RDKit is required for ligand preparation (pip install rdkit)"}
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": f"Invalid SMILES: {smiles}", "summary": f"Invalid SMILES: {smiles}"}
    mol = Chem.AddHs(mol)
    res = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
    if res != 0:
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3(), randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)

    sdf_path = work_dir / "ligand.sdf"
    writer = Chem.SDWriter(str(sdf_path))
    writer.write(mol)
    writer.close()

    pdbqt_path = work_dir / "ligand.pdbqt"

    # Try obabel conversion
    try:
        conv = _structure.subprocess.run(
            ["obabel", str(sdf_path), "-O", str(pdbqt_path), "--gen3d"],
            capture_output=True, text=True, timeout=30,
        )
        if conv.returncode == 0 and pdbqt_path.exists():
            return {"path": str(pdbqt_path), "mol": mol, "obabel_fallback": False}
    except FileNotFoundError:
        pass

    # Fallback: write a minimal PDBQT from coordinates
    # Note: lacks proper atom types and charges — adequate for scoring but
    # install Open Babel for production docking: conda install -c conda-forge openbabel
    conf = mol.GetConformer()
    lines = []
    for i, atom in enumerate(mol.GetAtoms()):
        pos = conf.GetAtomPosition(i)
        element = atom.GetSymbol()
        lines.append(
            f"ATOM  {i+1:5d}  {element:<3s} LIG A   1    "
            f"{pos.x:8.3f}{pos.y:8.3f}{pos.z:8.3f}  1.00  0.00    "
            f"{element:>2s}"
        )
    pdbqt_path.write_text("\n".join(lines) + "\n")
    return {"path": str(pdbqt_path), "mol": mol, "obabel_fallback": True}


def _detect_search_box(pdb_path: str) -> dict:
    """Compute a bounding-box centre and size from PDB ATOM coordinates.

    Returns ``{"center_x", "center_y", "center_z", "size_x", "size_y",
    "size_z"}`` with a 10 A padding on each side.
    """
    xs, ys, zs = [], [], []
    with open(pdb_path) as fh:
        for line in fh:
            if line.startswith(("ATOM", "HETATM")):
                try:
                    xs.append(float(line[30:38]))
                    ys.append(float(line[38:46]))
                    zs.append(float(line[46:54]))
                except (ValueError, IndexError):
                    continue
    if not xs:
        return {"error": "No atoms found in PDB", "summary": "No atoms found in PDB"}
    padding = 10.0
    return {
        "center_x": round((min(xs) + max(xs)) / 2, 2),
        "center_y": round((min(ys) + max(ys)) / 2, 2),
        "center_z": round((min(zs) + max(zs)) / 2, 2),
        "size_x": round(max(xs) - min(xs) + 2 * padding, 2),
        "size_y": round(max(ys) - min(ys) + 2 * padding, 2),
        "size_z": round(max(zs) - min(zs) + 2 * padding, 2),
    }


@registry.register(
    name="structure.dock",
    description="Molecular docking: dock a ligand (SMILES) into a target protein (PDB path or UniProt ID)",
    category="structure",
    parameters={
        "smiles": "Ligand SMILES string",
        "target_pdb": "Path to target PDB file or UniProt ID for AlphaFold fetch",
        "method": "Docking method: vina (default), diffdock, gnina",
        "n_poses": "Number of docking poses to generate (default 5)",
    },
    usage_guide=(
        "You want to predict how a small molecule binds to a protein target. "
        "Use Vina for fast local docking, DiffDock for GPU-accelerated deep-learning "
        "docking, or gnina for CNN-scored docking. Returns binding poses with "
        "predicted affinities."
    ),
)
def dock(smiles: str, target_pdb: str, method: str = "vina",
         n_poses: int = 5, **kwargs) -> dict:
    """Dock a ligand into a protein target.

    * method='vina'    — runs AutoDock Vina locally if installed, else submits
                         to cloud compute.
    * method='diffdock' — always submitted as cloud GPU job.
    * method='gnina'   — runs gnina locally if installed, else cloud.
    """
    import tempfile

    valid_methods = ("vina", "diffdock", "gnina")
    if method not in valid_methods:
        return {"error": f"Unknown docking method '{method}'. Choose from: {', '.join(valid_methods)}", "summary": f"Unknown docking method '{method}'. Choose from: {', '.join(valid_methods)}"}
    # Resolve target PDB
    target = _resolve_pdb(target_pdb)
    if "error" in target:
        return {"error": target["error"], "summary": f"Docking failed: {target['error']}"}
    pdb_path = target["path"]

    # GPU-only methods go straight to cloud
    if method == "diffdock":
        from tools.compute import submit_job
        job_result = submit_job(
            job_type="molecular_docking",
            params={
                "smiles": smiles,
                "target_pdb": pdb_path,
                "method": "diffdock",
                "n_poses": n_poses,
            },
            dry_run=kwargs.get("dry_run", True),
        )
        if "error" in job_result:
            return {
                "error": job_result["error"],
                "summary": f"DiffDock submission failed: {job_result['error']}",
            }
        return {
            "summary": f"DiffDock docking submitted for {smiles[:40]} into {Path(pdb_path).stem} ({n_poses} poses)",
            "method": "diffdock",
            "job": job_result,
        }

    # Vina / gnina — try local first
    work_dir = Path(tempfile.mkdtemp(prefix="ct_dock_"))

    # Prepare ligand
    lig = _prepare_ligand_pdbqt(smiles, work_dir)
    if "error" in lig:
        return {"error": lig["error"], "summary": f"Ligand preparation failed: {lig['error']}"}

    # Compute search box from target
    box = _detect_search_box(pdb_path)
    if "error" in box:
        return {"error": box["error"], "summary": f"Search box detection failed: {box['error']}"}

    binary = method  # "vina" or "gnina"
    output_path = work_dir / "docking_out.pdbqt"

    # Check if binary is available locally
    try:
        _structure.subprocess.run([binary, "--version"], capture_output=True, timeout=5)
        local_available = True
    except (FileNotFoundError, _structure.subprocess.TimeoutExpired):
        local_available = False

    if not local_available:
        # Submit as cloud job
        from tools.compute import submit_job
        job_result = submit_job(
            job_type="molecular_docking",
            params={
                "smiles": smiles,
                "target_pdb": pdb_path,
                "method": method,
                "n_poses": n_poses,
                "search_box": box,
            },
            dry_run=kwargs.get("dry_run", True),
        )
        if "error" in job_result:
            return {
                "error": job_result["error"],
                "summary": f"{method} not installed locally; cloud submission failed: {job_result['error']}",
            }
        return {
            "summary": (
                f"{method} not installed locally — submitted cloud docking job for "
                f"{smiles[:40]} into {Path(pdb_path).stem}"
            ),
            "method": method,
            "local": False,
            "job": job_result,
        }

    # Run locally
    cmd = [
        binary,
        "--receptor", pdb_path,
        "--ligand", lig["path"],
        "--center_x", str(box["center_x"]),
        "--center_y", str(box["center_y"]),
        "--center_z", str(box["center_z"]),
        "--size_x", str(box["size_x"]),
        "--size_y", str(box["size_y"]),
        "--size_z", str(box["size_z"]),
        "--num_modes", str(n_poses),
        "--out", str(output_path),
    ]

    try:
        proc = _structure.subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except _structure.subprocess.TimeoutExpired:
        return {"error": f"{method} timed out after 300s", "summary": "Docking timed out"}

    if proc.returncode != 0:
        return {"error": f"{method} failed: {proc.stderr[:500]}", "summary": "Docking failed"}

    # Parse output for binding affinities
    poses = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        # Vina output: mode | affinity | rmsd_lb | rmsd_ub
        if len(parts) >= 4:
            try:
                mode = int(parts[0])
                affinity = float(parts[1])
                rmsd_lb = float(parts[2])
                rmsd_ub = float(parts[3])
                poses.append({
                    "mode": mode,
                    "affinity_kcal_mol": affinity,
                    "rmsd_lb": rmsd_lb,
                    "rmsd_ub": rmsd_ub,
                })
            except (ValueError, IndexError):
                continue

    best = poses[0]["affinity_kcal_mol"] if poses else "N/A"

    obabel_note = ""
    if lig.get("obabel_fallback"):
        obabel_note = " (Note: Open Babel not installed — ligand PDBQT may lack proper atom types. Install: conda install -c conda-forge openbabel)"

    return {
        "summary": (
            f"Docked {smiles[:40]} into {Path(pdb_path).stem}: "
            f"best pose {best} kcal/mol ({len(poses)} poses){obabel_note}"
        ),
        "method": method,
        "local": True,
        "poses": poses,
        "output_path": str(output_path),
        "search_box": box,
    }
