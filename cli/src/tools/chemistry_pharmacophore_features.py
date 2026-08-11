"""chemistry.pharmacophore: SMARTS feature definitions + per-molecule detection. Split from tools/chemistry.py."""

PHARMACOPHORE_FEATURES = {
    "HBD": {
        "name": "Hydrogen Bond Donor",
        "smarts": ["[#7!H0&!$(N-[SX4](=O)(=O)[CX4](F)(F)F)]", "[#8!H0&!$([OH][C,S,P]=O)]", "[#16!H0]"],
    },
    "HBA": {
        "name": "Hydrogen Bond Acceptor",
        "smarts": ["[#7&!$([nH])&!$(N-N=O)]", "[$([O])&!$([OX2](C)C=O)]", "[#16&X2]"],
    },
    "Aromatic": {
        "name": "Aromatic Ring",
        "smarts": ["a1aaaaa1", "a1aaaa1"],
    },
    "Hydrophobic": {
        "name": "Hydrophobic",
        "smarts": ["[CH2X4,CH1X4,CH0X4]", "[$([cX3](:*):*)&!$([cX3](-[OH])-[OH])]"],
    },
    "PosIonizable": {
        "name": "Positive Ionizable",
        "smarts": ["[+,+2,+3,+4]", "[$([NX3&!$([NX3]-O)](-C)(-C)-C)]", "[$(n1cc[nH]c1)]"],
    },
    "NegIonizable": {
        "name": "Negative Ionizable",
        "smarts": ["[-,-2,-3,-4]", "[$([OH]-[CX3]=[OX1])]", "[$([OH]-[SX4](=[OX1])(=[OX1]))]"],
    },
}


def detect_features_per_molecule(mols: list, valid_smiles: list) -> list:
    """Detect pharmacophore feature counts for each molecule. Returns a list of
    {"smiles": ..., "features": {feature_type: count}} dicts."""
    from rdkit import Chem

    per_molecule_features = []
    for i, mol in enumerate(mols):
        mol_features = {}
        for feat_type, feat_def in PHARMACOPHORE_FEATURES.items():
            count = 0
            for smarts_str in feat_def["smarts"]:
                pattern = Chem.MolFromSmarts(smarts_str)
                if pattern is not None:
                    count += len(mol.GetSubstructMatches(pattern))
            mol_features[feat_type] = count
        per_molecule_features.append({"smiles": valid_smiles[i], "features": mol_features})
    return per_molecule_features
