"""chemistry.sar_analyze: structure-activity relationship correlation. Split from tools/chemistry.py."""
from tools import registry


@registry.register(
    name="chemistry.sar_analyze",
    description="Analyze structure-activity relationships for a set of compounds with activity data",
    category="chemistry",
    parameters={"compounds_path": "CSV with SMILES and activity columns"},
    usage_guide="You have a set of compounds with activity data and want to understand which molecular features drive potency. Use for medicinal chemistry optimization guidance.",
)
def sar_analyze(compounds_path: str, activity_col: str = "activity", **kwargs) -> dict:
    """Run SAR analysis on a compound set."""
    import pandas as pd
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    df = pd.read_csv(compounds_path)
    smiles_col = next((c for c in df.columns if c.lower() in ['smiles', 'canonical_smiles']), None)

    if smiles_col is None or activity_col not in df.columns:
        return {"error": "Need SMILES and activity columns", "summary": "Need SMILES and activity columns"}
    # Compute descriptors
    features = []
    for _, row in df.iterrows():
        mol = Chem.MolFromSmiles(row[smiles_col])
        if mol is None:
            continue
        features.append({
            "smiles": row[smiles_col],
            "activity": row[activity_col],
            "mw": Descriptors.MolWt(mol),
            "logp": Descriptors.MolLogP(mol),
            "tpsa": Descriptors.TPSA(mol),
            "hbd": Descriptors.NumHDonors(mol),
            "hba": Descriptors.NumHAcceptors(mol),
            "rotbonds": Descriptors.NumRotatableBonds(mol),
        })

    feat_df = pd.DataFrame(features)

    # Correlate descriptors with activity
    from scipy import stats
    correlations = {}
    for col in ["mw", "logp", "tpsa", "hbd", "hba", "rotbonds"]:
        r, p = stats.pearsonr(feat_df[col], feat_df["activity"])
        correlations[col] = {"r": round(r, 3), "p": round(p, 4)}

    return {
        "summary": f"SAR analysis on {len(feat_df)} compounds",
        "correlations": correlations,
        "n_compounds": len(feat_df),
    }
