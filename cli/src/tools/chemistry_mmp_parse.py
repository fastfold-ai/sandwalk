"""chemistry.mmp_analysis: compound loading + scaffold parsing. Split from tools/chemistry.py."""


def load_and_parse_compounds(compounds_csv: str | None, activity_col: str) -> dict:
    """Load compounds (from CSV or a built-in demo set) and compute Murcko scaffolds.

    Returns a dict with either an "error" key, or "parsed" (list of compound dicts)
    and "using_demo" (bool).
    """
    from rdkit import Chem
    from rdkit.Chem.Scaffolds import MurckoScaffold
    import pandas as pd

    if compounds_csv:
        try:
            df = pd.read_csv(compounds_csv)
        except Exception as e:
            return {"error": f"Could not read CSV: {e}", "summary": f"Failed to load {compounds_csv}"}
        smiles_col = next((c for c in df.columns if c.lower() in ["smiles", "canonical_smiles"]), None)
        if smiles_col is None:
            return {"error": "No SMILES column found (expected 'smiles' or 'canonical_smiles')", "summary": "No SMILES column found (expected 'smiles' or 'canonical_smiles')"}
        if activity_col not in df.columns:
            return {"error": f"Activity column '{activity_col}' not found. Available: {list(df.columns)}", "summary": f"Activity column '{activity_col}' not found. Available: {list(df.columns)}"}
    else:
        # Demo dataset: simple benzamide series
        demo_data = [
            ("c1ccc(C(=O)N)cc1", 5.2, "benzamide"),
            ("c1ccc(C(=O)N)cc1F", 6.1, "4-fluorobenzamide"),
            ("c1ccc(C(=O)N)cc1Cl", 5.8, "4-chlorobenzamide"),
            ("c1ccc(C(=O)N)cc1C", 5.5, "4-methylbenzamide"),
            ("c1ccc(C(=O)N)cc1OC", 6.4, "4-methoxybenzamide"),
            ("c1ccc(C(=O)N)cc1O", 6.0, "4-hydroxybenzamide"),
            ("c1ccc(C(=O)NC)cc1", 5.0, "N-methylbenzamide"),
            ("c1ccc(C(=O)NCC)cc1", 4.7, "N-ethylbenzamide"),
            ("c1ccc(C(=O)N)c(F)c1", 5.9, "3-fluorobenzamide"),
            ("c1cc(F)c(C(=O)N)cc1F", 6.8, "3,4-difluorobenzamide"),
        ]
        df = pd.DataFrame(demo_data, columns=["smiles", activity_col, "name"])
        smiles_col = "smiles"

    parsed = []
    for _, row in df.iterrows():
        mol = Chem.MolFromSmiles(row[smiles_col])
        if mol is None:
            continue
        try:
            scaffold = MurckoScaffold.GetScaffoldForMol(mol)
            scaffold_smi = Chem.MolToSmiles(scaffold)
        except Exception:
            scaffold_smi = "unknown"
        parsed.append({
            "smiles": row[smiles_col],
            "mol": mol,
            "activity": float(row[activity_col]),
            "scaffold": scaffold_smi,
            "name": row.get("name", row[smiles_col]),
        })

    if len(parsed) < 2:
        return {"error": "Need at least 2 valid compounds for MMP analysis", "summary": "Insufficient valid compounds for analysis"}

    return {"parsed": parsed, "using_demo": compounds_csv is None}
