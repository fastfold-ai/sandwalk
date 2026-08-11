"""chemistry.pairwise_similarity / similarity_search: fingerprint-based similarity. Split from tools/chemistry.py."""
from tools import chemistry as _chemistry
from tools import registry


@registry.register(
    name="chemistry.pairwise_similarity",
    description="Compute pairwise Tanimoto similarity matrix for a list of compounds (by name or SMILES)",
    category="chemistry",
    parameters={
        "compounds": "List of compound names or SMILES strings",
        "fingerprint": "Fingerprint type: 'morgan' (default, ECFP4) or 'maccs'",
    },
    usage_guide="You need to compute fingerprint similarity between a set of named compounds. Use when the question asks to 'compare similarity', 'cluster by scaffold', or 'compute Tanimoto' between specific compounds. Returns a full pairwise similarity matrix.",
)
def pairwise_similarity(compounds: list = None, fingerprint: str = "morgan", **kwargs) -> dict:
    """Compute pairwise Tanimoto similarity for a set of compounds."""
    if not compounds or len(compounds) < 2:
        return {"error": "Need at least 2 compounds", "summary": "Provide a list of 2+ compound names or SMILES"}

    from rdkit import Chem, DataStructs
    from rdkit.Chem import AllChem, MACCSkeys

    # Resolve names to SMILES and compute fingerprints
    resolved = []
    for cpd in compounds:
        smi = _chemistry._extract_smiles(cpd)
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            resolved.append({"name": cpd, "smiles": smi, "mol": None, "error": f"Invalid SMILES: {smi}"})
        else:
            resolved.append({"name": cpd, "smiles": Chem.MolToSmiles(mol), "mol": mol})

    # Compute fingerprints
    fps = []
    for r in resolved:
        if r["mol"] is None:
            fps.append(None)
        elif fingerprint == "maccs":
            fps.append(MACCSkeys.GenMACCSKeys(r["mol"]))
        else:
            fps.append(AllChem.GetMorganFingerprintAsBitVect(r["mol"], 2, nBits=2048))

    # Compute pairwise similarity matrix
    n = len(resolved)
    matrix = {}
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            if fps[i] is None or fps[j] is None:
                sim = 0.0
            else:
                sim = DataStructs.TanimotoSimilarity(fps[i], fps[j])
            key = f"{resolved[i]['name']} vs {resolved[j]['name']}"
            matrix[key] = round(sim, 4)
            pairs.append({
                "compound_a": resolved[i]["name"],
                "compound_b": resolved[j]["name"],
                "smiles_a": resolved[i]["smiles"],
                "smiles_b": resolved[j]["smiles"],
                "tanimoto": round(sim, 4),
            })

    # Sort by similarity
    pairs.sort(key=lambda x: -x["tanimoto"])

    # Cluster suggestion
    if pairs:
        most_similar = pairs[0]
        least_similar = pairs[-1]
    else:
        most_similar = least_similar = {}

    # Build readable matrix
    names = [r["name"] for r in resolved]
    matrix_rows = []
    for i in range(n):
        row = {}
        for j in range(n):
            if i == j:
                row[names[j]] = 1.0
            elif i < j:
                row[names[j]] = round(DataStructs.TanimotoSimilarity(fps[i], fps[j]), 4) if fps[i] and fps[j] else 0.0
            else:
                row[names[j]] = round(DataStructs.TanimotoSimilarity(fps[j], fps[i]), 4) if fps[i] and fps[j] else 0.0
        matrix_rows.append({"compound": names[i], **row})

    fp_label = "ECFP4 (Morgan r=2, 2048 bits)" if fingerprint == "morgan" else "MACCS keys (166 bits)"

    summary_lines = [
        f"Pairwise Tanimoto similarity ({fp_label}) for {n} compounds:",
    ]
    for p in pairs:
        summary_lines.append(f"  {p['compound_a']} vs {p['compound_b']}: {p['tanimoto']:.4f}")
    if most_similar:
        summary_lines.append(f"Most similar: {most_similar['compound_a']} & {most_similar['compound_b']} ({most_similar['tanimoto']:.4f})")
    if least_similar:
        summary_lines.append(f"Most different: {least_similar['compound_a']} & {least_similar['compound_b']} ({least_similar['tanimoto']:.4f})")

    return {
        "summary": "\n".join(summary_lines),
        "fingerprint_type": fp_label,
        "n_compounds": n,
        "pairs": pairs,
        "matrix": matrix_rows,
        "resolved_smiles": [{"name": r["name"], "smiles": r["smiles"]} for r in resolved],
    }


@registry.register(
    name="chemistry.similarity_search",
    description="Find similar compounds in a library using Tanimoto similarity on Morgan fingerprints",
    category="chemistry",
    parameters={"smiles": "Query SMILES", "library_path": "Path to compound library CSV", "top_n": "Number of hits"},
    usage_guide="You have a hit compound and want to find structurally similar analogs in a library. Use for SAR expansion or finding backup compounds with similar scaffolds.",
)
def similarity_search(smiles: str, library_path: str = None, top_n: int = 10, **kwargs) -> dict:
    """Search for similar compounds using fingerprint similarity."""
    smiles = _chemistry._extract_smiles(smiles)
    import pandas as pd
    from rdkit import Chem, DataStructs
    from rdkit.Chem import AllChem

    query_mol = Chem.MolFromSmiles(smiles)
    if query_mol is None:
        return {"error": f"Invalid SMILES: {smiles}", "summary": f"Invalid SMILES: {smiles}"}
    query_fp = AllChem.GetMorganFingerprintAsBitVect(query_mol, 2, nBits=2048)

    # Load library
    if library_path:
        lib = pd.read_csv(library_path)
    else:
        return {"error": "No compound library specified", "summary": "No compound library specified"}
    smiles_col = next((c for c in lib.columns if c.lower() in ['smiles', 'canonical_smiles']), None)
    if smiles_col is None:
        return {"error": "No SMILES column found in library", "summary": "No SMILES column found in library"}
    results = []
    for _, row in lib.iterrows():
        mol = Chem.MolFromSmiles(row[smiles_col])
        if mol is None:
            continue
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
        similarity = DataStructs.TanimotoSimilarity(query_fp, fp)
        results.append({
            "smiles": row[smiles_col],
            "similarity": similarity,
            **{k: row[k] for k in row.index if k != smiles_col},
        })

    results.sort(key=lambda x: -x["similarity"])
    top_hits = results[:top_n]

    return {
        "summary": f"Top {top_n} similar compounds (max Tanimoto={top_hits[0]['similarity']:.3f})" if top_hits else "No hits",
        "hits": top_hits,
        "library_size": len(results),
    }
