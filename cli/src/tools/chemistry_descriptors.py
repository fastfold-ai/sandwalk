"""chemistry.descriptors: RDKit molecular descriptor calculation. Split from tools/chemistry.py."""
from tools import registry

from tools import chemistry as _chemistry


@registry.register(
    name="chemistry.descriptors",
    description="Compute molecular descriptors and fingerprints for a compound from SMILES",
    category="chemistry",
    parameters={"smiles": "SMILES string"},
    usage_guide="You need molecular properties (MW, LogP, TPSA, Lipinski) for a compound. Use early in hit characterization to assess drug-likeness and physicochemical profile.",
)
def descriptors(smiles: str, **kwargs) -> dict:
    """Compute molecular properties from SMILES."""
    smiles = _chemistry._extract_smiles(smiles)
    from rdkit import Chem
    from rdkit.Chem import Descriptors, rdMolDescriptors

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": f"Invalid SMILES: {smiles}", "summary": f"Invalid SMILES: {smiles}"}
    props = {
        "smiles": smiles,
        "molecular_weight": Descriptors.MolWt(mol),
        "logp": Descriptors.MolLogP(mol),
        "hbd": Descriptors.NumHDonors(mol),
        "hba": Descriptors.NumHAcceptors(mol),
        "tpsa": Descriptors.TPSA(mol),
        "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
        "rings": Descriptors.RingCount(mol),
        "aromatic_rings": Descriptors.NumAromaticRings(mol),
        "heavy_atoms": mol.GetNumHeavyAtoms(),
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "num_stereocenters": len(Chem.FindMolChiralCenters(mol)),
    }

    # Lipinski Rule of 5
    props["lipinski_violations"] = sum([
        props["molecular_weight"] > 500,
        props["logp"] > 5,
        props["hbd"] > 5,
        props["hba"] > 10,
    ])

    # Molecular glue specific
    props["mw_logp_ratio"] = props["molecular_weight"] / (props["logp"] + 1e-6)
    props["tpsa_per_mw"] = props["tpsa"] / props["molecular_weight"]

    return {
        "summary": f"Molecular profile for {props['formula']} (MW={props['molecular_weight']:.1f}, "
                   f"LogP={props['logp']:.2f}, Lipinski violations={props['lipinski_violations']})",
        "properties": props,
    }
