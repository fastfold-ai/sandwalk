"""Imaging tool: structural fingerprint similarity as a morphological-similarity proxy."""

from tools import registry


@registry.register(
    name="imaging.morphology_similarity",
    description="Compare two compounds by structural fingerprint similarity (Morgan/MACCS Tanimoto) as a proxy for phenotypic similarity",
    category="imaging",
    parameters={
        "smiles_a": "SMILES string for compound A",
        "smiles_b": "SMILES string for compound B",
    },
    usage_guide="You want to compare two compounds by structural similarity as a proxy for phenotypic similarity. Uses Morgan fingerprints (radius=2, 2048 bits), MACCS keys, and physicochemical property comparison. Structural similarity correlates with morphological similarity for ~60% of compound pairs (Bray et al. 2017). For actual Cell Painting profile comparison, pre-computed profiles from JUMP would be needed.",
)
def morphology_similarity(smiles_a: str, smiles_b: str, **kwargs) -> dict:
    """Compare two compounds by morphological similarity.

    Uses RDKit Morgan fingerprints (radius=2, 2048 bits) as a structural proxy
    for morphological similarity. Structural similarity correlates with morphological
    similarity for ~60% of compound pairs (Bray et al., Nat Biotechnol 2017).
    Also computes MACCS keys similarity and physicochemical property comparison.
    """
    try:
        from rdkit import Chem, DataStructs
        from rdkit.Chem import AllChem, Descriptors, MACCSkeys, rdMolDescriptors
    except ImportError:
        return {
            "error": "RDKit is required for morphology similarity. Install with: pip install rdkit",
            "summary": "RDKit not installed — needed for fingerprint-based similarity",
        }

    mol_a = Chem.MolFromSmiles(smiles_a)
    mol_b = Chem.MolFromSmiles(smiles_b)

    if mol_a is None:
        return {"error": f"Invalid SMILES for compound A: {smiles_a}", "summary": f"Could not parse SMILES: {smiles_a}"}
    if mol_b is None:
        return {"error": f"Invalid SMILES for compound B: {smiles_b}", "summary": f"Could not parse SMILES: {smiles_b}"}

    # Morgan fingerprint similarity (main metric)
    fp_a = AllChem.GetMorganFingerprintAsBitVect(mol_a, 2, nBits=2048)
    fp_b = AllChem.GetMorganFingerprintAsBitVect(mol_b, 2, nBits=2048)
    morgan_sim = DataStructs.TanimotoSimilarity(fp_a, fp_b)

    # MACCS keys similarity (complementary metric)
    maccs_a = MACCSkeys.GenMACCSKeys(mol_a)
    maccs_b = MACCSkeys.GenMACCSKeys(mol_b)
    maccs_sim = DataStructs.TanimotoSimilarity(maccs_a, maccs_b)

    # Dice similarity (alternative metric)
    dice_sim = DataStructs.DiceSimilarity(fp_a, fp_b)

    # Physicochemical property comparison
    def _get_props(mol):
        return {
            "mw": round(Descriptors.MolWt(mol), 2),
            "logp": round(Descriptors.MolLogP(mol), 2),
            "tpsa": round(Descriptors.TPSA(mol), 2),
            "hba": Descriptors.NumHAcceptors(mol),
            "hbd": Descriptors.NumHDonors(mol),
            "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
            "aromatic_rings": Descriptors.NumAromaticRings(mol),
            "fsp3": round(rdMolDescriptors.CalcFractionCSP3(mol), 3),
        }

    props_a = _get_props(mol_a)
    props_b = _get_props(mol_b)

    # Compute property similarity (normalized)
    prop_diffs = {}
    shared_features = []
    for key in props_a:
        diff = abs(props_a[key] - props_b[key])
        prop_diffs[key] = round(diff, 3)

        # Flag shared features
        if key == "mw" and diff < 50:
            shared_features.append("similar molecular weight")
        elif key == "logp" and diff < 1:
            shared_features.append("similar lipophilicity")
        elif key == "tpsa" and diff < 20:
            shared_features.append("similar polarity")
        elif key == "aromatic_rings" and diff == 0:
            shared_features.append(f"same aromatic ring count ({props_a[key]})")
        elif key == "hbd" and diff == 0 and props_a[key] > 0:
            shared_features.append(f"same H-bond donors ({props_a[key]})")

    # Infer morphological similarity class
    combined_sim = 0.6 * morgan_sim + 0.3 * maccs_sim + 0.1 * dice_sim
    if combined_sim > 0.85:
        sim_class = "highly similar"
        morphology_prediction = "Very likely similar morphological profiles"
    elif combined_sim > 0.6:
        sim_class = "moderately similar"
        morphology_prediction = "Possibly similar morphological effects"
    elif combined_sim > 0.4:
        sim_class = "weakly similar"
        morphology_prediction = "Some shared structural features; morphology may differ"
    else:
        sim_class = "dissimilar"
        morphology_prediction = "Likely different morphological profiles"

    # Heuristic mechanism class
    def _mechanism_class(props):
        if props["aromatic_rings"] >= 3 and props["hba"] >= 2:
            return "kinase_inhibitor_like"
        elif props["mw"] < 600 and props["logp"] < 2:
            return "polar_small_molecule"
        elif props["mw"] > 800:
            return "macrocycle_like"
        else:
            return "standard_small_molecule"

    mech_a = _mechanism_class(props_a)
    mech_b = _mechanism_class(props_b)

    summary = (
        f"Morphological similarity between compounds: {combined_sim:.2f} ({sim_class}). "
        f"Morgan Tanimoto: {morgan_sim:.3f}, MACCS: {maccs_sim:.3f}. "
        f"{morphology_prediction}"
    )
    if shared_features:
        summary += f". Shared: {', '.join(shared_features[:4])}"

    return {
        "summary": summary,
        "similarity_scores": {
            "morgan_tanimoto": round(morgan_sim, 4),
            "maccs_tanimoto": round(maccs_sim, 4),
            "dice": round(dice_sim, 4),
            "combined": round(combined_sim, 4),
        },
        "similarity_class": sim_class,
        "morphology_prediction": morphology_prediction,
        "shared_features": shared_features,
        "compound_a": {
            "smiles": smiles_a,
            "properties": props_a,
            "mechanism_class": mech_a,
        },
        "compound_b": {
            "smiles": smiles_b,
            "properties": props_b,
            "mechanism_class": mech_b,
        },
        "property_differences": prop_diffs,
    }
