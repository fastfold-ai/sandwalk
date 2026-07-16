"""structure.ternary_predict / batch_screen: DeepTernary via the TernaryPred sister project.

Split from tools/structure.py. Reads ``TERNARYPRED_DIR`` indirectly via the ``tools.structure``
hub module so that ``patch("tools.structure.TERNARYPRED_DIR")`` in tests continues to work
regardless of which submodule performs the lookup.
"""

import subprocess
import sys

from tools import registry
from tools import structure as _structure


@registry.register(
    name="structure.ternary_predict",
    description="Predict ternary complex structure (E3 ligase + compound + target) using DeepTernary (requires TernaryPred installation)",
    category="structure",
    parameters={
        "smiles": "Compound SMILES string",
        "target_pdb": "Path to target protein PDB",
        "e3": "E3 ligase: CRBN or VHL",
    },
    usage_guide="You want to predict how a molecular glue or PROTAC forms a ternary complex between E3 ligase and target. Use when you have a compound SMILES and target structure. Requires TernaryPred installation.",
)
def ternary_predict(smiles: str, target_pdb: str, e3: str = "CRBN",
                    name: str = "prediction", **kwargs) -> dict:
    """Predict ternary complex using DeepTernary via TernaryPred wrapper."""
    ternarypred_dir = _structure.TERNARYPRED_DIR
    script = ternarypred_dir / "scripts" / "predict_deepternary.py"
    e3_path = ternarypred_dir / "data" / "e3_structures" / f"{'crbn_5fqd' if e3 == 'CRBN' else 'vhl_4w9h'}.pdb"

    if not script.exists():
        return {
            "error": (
                f"TernaryPred not installed. This tool requires the TernaryPred sister project.\n"
                f"Install: git clone git@github.com:celltype/TernaryPred.git {ternarypred_dir}"
            ),
            "summary": "Ternary prediction unavailable — TernaryPred not installed",
        }

    cmd = [
        sys.executable, str(script), "single",
        "--smiles", smiles,
        "--e3", str(e3_path),
        "--target", target_pdb,
        "--name", name,
        "--device", "cuda",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        return {"error": f"DeepTernary failed: {result.stderr[:500]}", "summary": f"DeepTernary failed: {result.stderr[:500]}"}
    return {
        "summary": f"Ternary complex predicted for {name}",
        "stdout": result.stdout,
        "e3": e3,
    }


@registry.register(
    name="structure.batch_screen",
    description="Screen compounds against a protein target panel for ternary compatibility (requires TernaryPred installation)",
    category="structure",
    parameters={
        "compounds_csv": "CSV with compound_id and smiles columns",
        "targets_csv": "CSV with target_id and structure_path columns",
        "e3": "E3 ligase: CRBN or VHL",
    },
    usage_guide="You need to screen many compounds against many targets for ternary complex formation. Use for large-scale virtual screening campaigns. Long-running — launches background process.",
)
def batch_screen(compounds_csv: str, targets_csv: str, e3: str = "CRBN",
                 max_compounds: int = None, max_targets: int = None, **kwargs) -> dict:
    """Batch ternary screening via TernaryPred."""
    ternarypred_dir = _structure.TERNARYPRED_DIR
    script = ternarypred_dir / "scripts" / "predict_deepternary.py"
    e3_path = ternarypred_dir / "data" / "e3_structures" / f"{'crbn_5fqd' if e3 == 'CRBN' else 'vhl_4w9h'}.pdb"

    if not script.exists():
        return {
            "error": (
                f"TernaryPred not installed. This tool requires the TernaryPred sister project.\n"
                f"Install: git clone git@github.com:celltype/TernaryPred.git {ternarypred_dir}"
            ),
            "summary": "Batch screening unavailable — TernaryPred not installed",
        }

    cmd = [
        sys.executable, str(script), "batch",
        "--compounds", compounds_csv,
        "--targets", targets_csv,
        "--e3", str(e3_path),
        "--outdir", str(ternarypred_dir / "predictions" / "ternary_complexes"),
        "--resume",
    ]
    if max_compounds:
        cmd += ["--max-compounds", str(max_compounds)]
    if max_targets:
        cmd += ["--max-targets", str(max_targets)]

    # This is a long-running process — run in background
    result = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return {
        "summary": f"Batch screening started (PID: {result.pid})",
        "pid": result.pid,
        "note": "Long-running process. Check TernaryPred/predictions/ for results.",
    }
