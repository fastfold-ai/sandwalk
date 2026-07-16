"""structure.binding_site: pocket detection via fpocket or geometric heuristics.

Split from tools/structure.py. Reads ``subprocess`` indirectly via the ``tools.structure``
hub module so that ``patch("tools.structure.subprocess")`` in tests continues to work
regardless of which submodule performs the call.
"""

from pathlib import Path

from tools import registry
from tools import structure as _structure
from tools.structure_fetch import _resolve_pdb


def _geometric_pocket_detection(pdb_path: str, min_residues: int = 5,
                                 distance_cutoff: float = 8.0) -> list[dict]:
    """Simple geometric pocket detection from PDB coordinates.

    Parses ATOM records, identifies residues with buried atoms (low
    neighbor-averaged solvent exposure), and clusters them by spatial
    proximity.  Returns a list of pocket dicts sorted by size.
    """
    import math

    # Parse atoms
    atoms = []
    with open(pdb_path) as fh:
        for line in fh:
            if not line.startswith("ATOM"):
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                resname = line[17:20].strip()
                resid = int(line[22:26])
                chain = line[21]
                atoms.append({
                    "x": x, "y": y, "z": z,
                    "resname": resname, "resid": resid, "chain": chain,
                })
            except (ValueError, IndexError):
                continue

    if len(atoms) < 10:
        return []

    # Compute centre of mass
    cx = sum(a["x"] for a in atoms) / len(atoms)
    cy = sum(a["y"] for a in atoms) / len(atoms)
    cz = sum(a["z"] for a in atoms) / len(atoms)

    # For each residue, compute distance to COM and local density
    residue_coords = {}
    for a in atoms:
        key = (a["chain"], a["resid"])
        if key not in residue_coords:
            residue_coords[key] = {"xs": [], "ys": [], "zs": [],
                                    "resname": a["resname"], "chain": a["chain"],
                                    "resid": a["resid"]}
        residue_coords[key]["xs"].append(a["x"])
        residue_coords[key]["ys"].append(a["y"])
        residue_coords[key]["zs"].append(a["z"])

    # Compute residue centres
    residues = []
    for _key, rc in residue_coords.items():
        rx = sum(rc["xs"]) / len(rc["xs"])
        ry = sum(rc["ys"]) / len(rc["ys"])
        rz = sum(rc["zs"]) / len(rc["zs"])
        dist_to_com = math.sqrt((rx - cx)**2 + (ry - cy)**2 + (rz - cz)**2)
        residues.append({
            "chain": rc["chain"], "resid": rc["resid"], "resname": rc["resname"],
            "x": rx, "y": ry, "z": rz, "dist_to_com": dist_to_com,
        })

    # Identify cavity residues: not too close to COM (core), not too far (surface)
    dists = [r["dist_to_com"] for r in residues]
    if not dists:
        return []
    median_dist = sorted(dists)[len(dists) // 2]
    cavity_residues = [
        r for r in residues
        if median_dist * 0.4 < r["dist_to_com"] < median_dist * 1.2
    ]

    if len(cavity_residues) < min_residues:
        cavity_residues = sorted(residues, key=lambda r: abs(r["dist_to_com"] - median_dist))[:max(min_residues, len(residues) // 4)]

    # Simple clustering: greedy single-linkage
    clusters = []
    assigned = set()
    for i, res in enumerate(cavity_residues):
        if i in assigned:
            continue
        cluster = [res]
        assigned.add(i)
        for j, other in enumerate(cavity_residues):
            if j in assigned:
                continue
            d = math.sqrt((res["x"] - other["x"])**2 +
                          (res["y"] - other["y"])**2 +
                          (res["z"] - other["z"])**2)
            if d < distance_cutoff:
                cluster.append(other)
                assigned.add(j)
        if len(cluster) >= min_residues:
            clusters.append(cluster)

    # Sort clusters by size descending
    clusters.sort(key=lambda c: len(c), reverse=True)

    pockets = []
    for idx, cluster in enumerate(clusters[:5]):  # top 5 pockets
        xs = [r["x"] for r in cluster]
        ys = [r["y"] for r in cluster]
        zs = [r["z"] for r in cluster]

        # Approximate volume as bounding box volume
        vol = (max(xs) - min(xs)) * (max(ys) - min(ys)) * (max(zs) - min(zs))

        # Druggability heuristic: more residues + larger volume + hydrophobic
        # residues are better
        hydrophobic = {"ALA", "VAL", "LEU", "ILE", "PHE", "TRP", "MET", "PRO"}
        n_hydrophobic = sum(1 for r in cluster if r["resname"] in hydrophobic)
        druggability = min(1.0, (len(cluster) / 20) * 0.5 + (n_hydrophobic / max(len(cluster), 1)) * 0.5)

        pockets.append({
            "pocket_id": idx + 1,
            "n_residues": len(cluster),
            "residue_ids": [f"{r['chain']}:{r['resname']}{r['resid']}" for r in cluster],
            "center": {
                "x": round(sum(xs) / len(xs), 2),
                "y": round(sum(ys) / len(ys), 2),
                "z": round(sum(zs) / len(zs), 2),
            },
            "volume_approx_A3": round(vol, 1),
            "druggability_score": round(druggability, 3),
        })

    return pockets


@registry.register(
    name="structure.binding_site",
    description="Detect binding pockets in a protein structure using geometric analysis or fpocket",
    category="structure",
    parameters={
        "pdb_path": "Path to PDB file or UniProt ID for AlphaFold fetch",
        "method": "Detection method: fpocket (default), geometric",
    },
    usage_guide=(
        "You want to find druggable binding pockets in a protein structure. "
        "Use before docking to identify where to focus. fpocket is preferred "
        "if installed; geometric fallback uses coordinate-based clustering."
    ),
)
def binding_site(pdb_path: str, method: str = "fpocket", **kwargs) -> dict:
    """Detect binding pockets in a protein structure.

    * method='fpocket'   — runs fpocket locally if installed, falls back to
                           geometric detection.
    * method='geometric' — pure coordinate-based pocket detection.
    """
    valid_methods = ("fpocket", "geometric")
    if method not in valid_methods:
        return {"error": f"Unknown method '{method}'. Choose from: {', '.join(valid_methods)}", "summary": f"Unknown method '{method}'. Choose from: {', '.join(valid_methods)}"}
    # Resolve PDB path (may be UniProt ID)
    target = _resolve_pdb(pdb_path)
    if "error" in target:
        return {"error": target["error"], "summary": f"Pocket detection failed: {target['error']}"}
    resolved_path = target["path"]
    protein_name = Path(resolved_path).stem

    if method == "fpocket":
        # Try running fpocket
        try:
            proc = _structure.subprocess.run(
                ["fpocket", "-f", resolved_path],
                capture_output=True, text=True, timeout=120,
            )
            if proc.returncode == 0:
                # Parse fpocket output
                out_dir = Path(resolved_path).parent / f"{protein_name}_out"
                info_file = out_dir / f"{protein_name}_info.txt"
                pockets = []

                if info_file.exists():
                    current_pocket = {}
                    for line in info_file.read_text().splitlines():
                        line = line.strip()
                        if line.startswith("Pocket"):
                            if current_pocket:
                                pockets.append(current_pocket)
                            pocket_num = line.split()[1].rstrip(":")
                            current_pocket = {"pocket_id": int(pocket_num)}
                        elif "Score" in line and ":" in line:
                            key, val = line.split(":", 1)
                            try:
                                current_pocket[key.strip().lower().replace(" ", "_")] = float(val.strip())
                            except ValueError:
                                current_pocket[key.strip().lower().replace(" ", "_")] = val.strip()
                        elif "Volume" in line and ":" in line:
                            key, val = line.split(":", 1)
                            try:
                                current_pocket["volume_A3"] = float(val.strip())
                            except ValueError:
                                pass
                    if current_pocket:
                        pockets.append(current_pocket)

                if pockets:
                    top = pockets[0]
                    vol_str = f"vol={top.get('volume_A3', '?')}A^3" if "volume_A3" in top else ""
                    return {
                        "summary": (
                            f"Found {len(pockets)} binding pocket(s) in {protein_name} (fpocket): "
                            f"site 1 ({vol_str})"
                        ),
                        "method": "fpocket",
                        "pockets": pockets,
                    }
        except (FileNotFoundError, _structure.subprocess.TimeoutExpired):
            pass  # Fall through to geometric

    # Geometric fallback
    pockets = _geometric_pocket_detection(resolved_path)

    if not pockets:
        return {
            "summary": f"No binding pockets detected in {protein_name}",
            "method": "geometric",
            "pockets": [],
        }

    top = pockets[0]
    return {
        "summary": (
            f"Found {len(pockets)} binding pocket(s) in {protein_name}: "
            f"site 1 (vol={top['volume_approx_A3']:.0f}A^3, "
            f"druggability={top['druggability_score']:.2f})"
        ),
        "method": "geometric",
        "pockets": pockets,
    }
