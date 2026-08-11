"""chemistry.pharmacophore: pharmacophore model generation from active compounds. Split from tools/chemistry.py."""
from tools import registry
from tools import chemistry as _chemistry
from tools.chemistry_pharmacophore_features import PHARMACOPHORE_FEATURES, detect_features_per_molecule


@registry.register(
    name="chemistry.pharmacophore",
    description="Generate a pharmacophore model from a set of active compounds identifying common molecular features",
    category="chemistry",
    parameters={
        "smiles_list": "List of SMILES strings for active compounds",
        "method": "Analysis method: 'common_features' (default) or 'fingerprints'",
    },
    usage_guide="You have a set of active compounds and want to identify the common pharmacophoric features that drive activity. Use for understanding SAR, virtual screening, and lead optimization. Identifies shared HBD, HBA, aromatic, hydrophobic, and ionizable features across the compound set.",
)
def pharmacophore(smiles_list: list = None, method: str = "common_features", **kwargs) -> dict:
    """Generate a pharmacophore model from a set of active compounds.

    Identifies common pharmacophore features (HBD, HBA, Aromatic, Hydrophobic,
    PosIonizable, NegIonizable) across the compound set and optionally generates
    2D pharmacophore fingerprints for consensus scoring.
    """
    from rdkit import Chem, DataStructs

    if not smiles_list or len(smiles_list) < 2:
        return {"error": "Need at least 2 SMILES strings", "summary": "Pharmacophore analysis requires at least 2 compounds"}

    smiles_list = [_chemistry._extract_smiles(smi) for smi in smiles_list]

    mols, valid_smiles, invalid = [], [], []
    for smi in smiles_list:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            invalid.append(smi)
        else:
            mols.append(mol)
            valid_smiles.append(smi)

    if len(mols) < 2:
        return {
            "error": f"Only {len(mols)} valid molecule(s) — need at least 2",
            "summary": "Insufficient valid molecules for pharmacophore analysis",
            "invalid_smiles": invalid,
        }

    n_compounds = len(mols)
    per_molecule_features = detect_features_per_molecule(mols, valid_smiles)

    feature_types = list(PHARMACOPHORE_FEATURES.keys())
    common_features = []
    feature_distribution = {}

    for feat_type in feature_types:
        counts = [mf["features"][feat_type] for mf in per_molecule_features]
        min_count, max_count = min(counts), max(counts)
        mean_count = sum(counts) / len(counts)
        present_in = sum(1 for c in counts if c > 0)
        frequency = present_in / n_compounds

        feature_distribution[feat_type] = {
            "name": PHARMACOPHORE_FEATURES[feat_type]["name"],
            "min_count": min_count,
            "max_count": max_count,
            "mean_count": round(mean_count, 1),
            "present_in_n": present_in,
            "frequency": round(frequency, 3),
        }

        if min_count > 0:
            common_features.append({
                "type": feat_type,
                "name": PHARMACOPHORE_FEATURES[feat_type]["name"],
                "min_count": min_count,
                "conserved": min_count == max_count,
                "frequency": 1.0,
            })

    pharm_fp_similarity = None
    if method in ("fingerprints", "both"):
        try:
            from rdkit.Chem.Pharm2D import Generate, Gobbi_Pharm2D

            factory = Gobbi_Pharm2D.factory
            fps = [Generate.Gen2DFingerprint(mol, factory) for mol in mols]

            sim_sum, sim_count = 0.0, 0
            for i in range(len(fps)):
                for j in range(i + 1, len(fps)):
                    sim_sum += DataStructs.TanimotoSimilarity(fps[i], fps[j])
                    sim_count += 1
            pharm_fp_similarity = round(sim_sum / sim_count, 3) if sim_count > 0 else 0.0
        except Exception:
            pharm_fp_similarity = None  # Gobbi_Pharm2D not available

    common_frac = len(common_features) / len(feature_types) if feature_types else 0.0

    variance_scores = []
    for feat_type in feature_types:
        counts = [mf["features"][feat_type] for mf in per_molecule_features]
        if max(counts) > 0:
            variance_scores.append(1.0 - (max(counts) - min(counts)) / max(counts))

    consistency = sum(variance_scores) / len(variance_scores) if variance_scores else 0.0
    consensus_score = round((common_frac * 0.6 + consistency * 0.4), 3)

    common_desc = [f"{cf['min_count']} {cf['name']}" for cf in common_features]
    summary_parts = [f"Pharmacophore from {n_compounds} compounds: {len(common_features)} common features"]
    if common_desc:
        summary_parts[0] += f" ({', '.join(common_desc)})"
    summary_parts.append(f"Consensus score: {consensus_score}")
    if pharm_fp_similarity is not None:
        summary_parts.append(f"Mean pharmacophore fingerprint similarity: {pharm_fp_similarity}")

    result = {
        "summary": "\n".join(summary_parts),
        "n_compounds": n_compounds,
        "n_valid": len(mols),
        "common_features": common_features,
        "feature_distribution": feature_distribution,
        "per_molecule_features": per_molecule_features,
        "consensus_score": consensus_score,
        "method": method,
    }
    if invalid:
        result["invalid_smiles"] = invalid
    if pharm_fp_similarity is not None:
        result["pharmacophore_fp_similarity"] = pharm_fp_similarity

    return result
