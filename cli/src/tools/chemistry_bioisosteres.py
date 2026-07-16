"""chemistry.scaffold_hop: functional-group and ring bioisostere reference data + matching. Split from tools/chemistry.py."""

# Each entry: (name, smarts, bioisosteres)
FG_DEFINITIONS = [
    ("carboxylic_acid", "[CX3](=O)[OX2H1]", [
        {"replacement": "tetrazole", "smiles_fragment": "c1nnn[nH]1",
         "rationale": "Classic carboxylic acid bioisostere — similar pKa, improved metabolic stability and permeability"},
        {"replacement": "acyl sulfonamide", "smiles_fragment": "C(=O)NS(=O)=O",
         "rationale": "Acidic NH mimics carboxylate — good for oral bioavailability"},
        {"replacement": "hydroxamic acid", "smiles_fragment": "C(=O)NO",
         "rationale": "Maintains H-bond donor/acceptor pattern — also a zinc-binding group"},
    ]),
    ("amide", "[NX3][CX3](=[OX1])[#6]", [
        {"replacement": "sulfonamide", "smiles_fragment": "NS(=O)(=O)",
         "rationale": "Similar geometry and H-bonding — often improved metabolic stability"},
        {"replacement": "urea", "smiles_fragment": "NC(=O)N",
         "rationale": "Additional H-bond donor — can improve target binding"},
        {"replacement": "reversed amide", "smiles_fragment": "C(=O)N (reversed)",
         "rationale": "Switching C(=O)NH to NHC(=O) — changes metabolic soft spot"},
        {"replacement": "1,2,4-oxadiazole", "smiles_fragment": "c1nonc1",
         "rationale": "Planar amide bioisostere — improved metabolic stability"},
    ]),
    ("phenyl", "c1ccccc1", [
        {"replacement": "pyridine", "smiles_fragment": "c1ccncc1",
         "rationale": "Introduces H-bond acceptor — improves solubility and can modulate pKa"},
        {"replacement": "pyrimidine", "smiles_fragment": "c1ncncc1",
         "rationale": "Two nitrogen atoms — further improved solubility vs pyridine"},
        {"replacement": "cyclohexane", "smiles_fragment": "C1CCCCC1",
         "rationale": "sp3-rich replacement — escape flatness, improve Fsp3 and solubility (Lovering)"},
        {"replacement": "thiophene", "smiles_fragment": "c1ccsc1",
         "rationale": "5-membered aromatic — different vector geometry, often similar binding"},
    ]),
    ("ester", "[#6][CX3](=O)[OX2][#6]", [
        {"replacement": "amide", "smiles_fragment": "C(=O)N",
         "rationale": "Much more metabolically stable — standard ester prodrug reversal"},
        {"replacement": "oxadiazole", "smiles_fragment": "c1nonn1",
         "rationale": "Planar ester bioisostere — metabolically stable"},
    ]),
    ("sulfonamide", "[NX3]S(=O)(=O)", [
        {"replacement": "amide", "smiles_fragment": "NC(=O)",
         "rationale": "Simpler, often similar activity — different metabolic profile"},
        {"replacement": "reverse sulfonamide", "smiles_fragment": "S(=O)(=O)N (reversed)",
         "rationale": "Switch N and C sides of sulfonamide"},
    ]),
    ("hydroxyl", "[OX2H]", [
        {"replacement": "fluorine", "smiles_fragment": "F",
         "rationale": "Similar size, H-bond acceptor only — blocks metabolic oxidation site"},
        {"replacement": "amine", "smiles_fragment": "N",
         "rationale": "H-bond donor and acceptor — different pKa profile"},
        {"replacement": "methoxy", "smiles_fragment": "OC",
         "rationale": "Caps the OH — blocks glucuronidation, changes H-bonding"},
    ]),
    ("nitrile", "[CX2]#[NX1]", [
        {"replacement": "isoxazole", "smiles_fragment": "c1ccon1",
         "rationale": "Ring-based CN mimic — similar dipole and H-bond accepting"},
    ]),
    ("fluorine", "[F]", [
        {"replacement": "chlorine", "smiles_fragment": "Cl",
         "rationale": "Larger halogen — increased lipophilicity, different steric profile"},
        {"replacement": "hydrogen", "smiles_fragment": "[H]",
         "rationale": "Remove halogen — simplify molecule, assess fluorine contribution"},
        {"replacement": "trifluoromethyl", "smiles_fragment": "C(F)(F)F",
         "rationale": "Strongly electron-withdrawing — metabolically stable, increases lipophilicity"},
    ]),
]

RING_REPLACEMENTS = {
    "c1ccccc1": [  # benzene
        ("c1ccncc1", "phenyl -> pyridyl (N-walk around ring)"),
        ("c1ccoc1", "phenyl -> furanyl (ring contraction)"),
        ("c1ccsc1", "phenyl -> thiophenyl (5-mem heterocycle)"),
        ("C1CCCCC1", "phenyl -> cyclohexyl (sp3 escape)"),
        ("c1cc[nH]c1", "phenyl -> pyrrolyl (electron-rich 5-mem)"),
    ],
    "c1ccncc1": [  # pyridine
        ("c1ccccc1", "pyridyl -> phenyl (remove N)"),
        ("c1ncncc1", "pyridyl -> pyrimidyl (add N)"),
        ("c1ccnnc1", "pyridyl -> pyridazinyl (adjacent N)"),
    ],
    "c1cc[nH]c1": [  # pyrrole
        ("c1ccoc1", "pyrrolyl -> furanyl"),
        ("c1ccsc1", "pyrrolyl -> thiophenyl"),
    ],
}


def detect_functional_groups(mol) -> tuple[list, list]:
    """Returns (detected_groups, all_bioisosteres)."""
    from rdkit import Chem

    detected_groups = []
    all_bioisosteres = []
    for fg_name, smarts, bioisosteres in FG_DEFINITIONS:
        pattern = Chem.MolFromSmarts(smarts)
        if pattern is None:
            continue
        matches = mol.GetSubstructMatches(pattern)
        if matches:
            detected_groups.append({"group": fg_name, "count": len(matches), "atom_indices": [list(m) for m in matches]})
            for bio in bioisosteres:
                all_bioisosteres.append({"original_group": fg_name, **bio})
    return detected_groups, all_bioisosteres


def suggest_scaffold_replacements(scaffold_smi: str) -> list:
    from rdkit import Chem

    scaffold_replacements = []
    if scaffold_smi == "N/A":
        return scaffold_replacements

    scaf_mol = Chem.MolFromSmiles(scaffold_smi)
    if not scaf_mol:
        return scaffold_replacements

    for ring_smi, replacements in RING_REPLACEMENTS.items():
        ring_pat = Chem.MolFromSmarts(ring_smi)
        if ring_pat and scaf_mol.HasSubstructMatch(ring_pat):
            for repl_smi, description in replacements:
                scaffold_replacements.append({"original_ring": ring_smi, "replacement_ring": repl_smi, "description": description})
    return scaffold_replacements
