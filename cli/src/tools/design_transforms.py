"""Bioisosteric transform application for design.suggest_modifications."""

from tools.design_scoring import (
    _compute_properties,
    _lipinski_violations,
    _property_deltas,
    _score_for_objective,
)

# Common medicinal chemistry transformations: (SMARTS_pattern, SMARTS_replacement, description)
# Each entry: (name, smarts_from, list_of_replacements)
_MEDCHEM_TRANSFORMS = [
    # Halogen walks
    ("F_to_Cl", "[cH0:1][F:2]", "[cH0:1][Cl]", "F->Cl: increase lipophilicity and steric bulk"),
    ("F_to_H", "[cH0:1][F:2]", "[cH:1]", "F->H: remove halogen, reduce MW"),
    ("Cl_to_F", "[cH0:1][Cl:2]", "[cH0:1][F]", "Cl->F: reduce lipophilicity, metabolic block"),
    # Alkyl modifications
    ("Me_to_Et", "[CH3:1]([#6:2])", "[CH2:1]([#6:2])C", "Me->Et: increase steric bulk, explore SAR"),
    ("OH_to_OMe", "[c:1][OH:2]", "[c:1]OC", "OH->OMe: cap phenol, block glucuronidation"),
    ("OMe_to_OH", "[c:1][O:2][CH3]", "[c:1][OH]", "OMe->OH: add H-bond donor, improve solubility"),
    # N-modifications
    ("NH_to_NMe", "[NH2:1]", "[NH:1]C", "NH2->NHMe: reduce basicity, improve metabolic stability"),
    ("NMe_to_NH", "[NH:1]([CH3])", "[NH2:1]", "NHMe->NH2: simplify, add H-bond donor"),
    # Ring modifications
    ("phenyl_to_pyridine", "[c:1]1[c:2][c:3][c:4][c:5][cH:6]1", "[c:1]1[c:2][c:3][c:4][c:5][n:6]1",
     "phenyl->pyridyl: improve solubility, add H-bond acceptor"),
]

_SIMPLE_ADDITIONS = [
    ("add_F", "F", "Add fluorine — metabolic blocker, minimal size increase"),
    ("add_OH", "O", "Add hydroxyl — improve solubility, add H-bond donor"),
    ("add_NH2", "N", "Add amine — add H-bond donor, potential salt formation"),
    ("add_Me", "C", "Add methyl — explore steric effects, fill hydrophobic pocket"),
]


def _apply_medchem_transforms(mol, parent_props: dict, objective: str, seen_smiles: set) -> list[dict]:
    """Apply each reaction-SMARTS transform and score the resulting products."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    suggestions = []
    for name, smarts_from, smarts_to, description in _MEDCHEM_TRANSFORMS:
        try:
            pattern = Chem.MolFromSmarts(smarts_from)
            if pattern is None or not mol.HasSubstructMatch(pattern):
                continue

            rxn = AllChem.ReactionFromSmarts(f"{smarts_from}>>{smarts_to}")
            if rxn is None:
                continue

            products = rxn.RunReactants((mol,))
            for product_set in products:
                for product in product_set:
                    try:
                        Chem.SanitizeMol(product)
                        product_smi = Chem.MolToSmiles(product)
                        if product_smi in seen_smiles:
                            continue
                        seen_smiles.add(product_smi)

                        child_props = _compute_properties(product)
                        suggestions.append({
                            "smiles": product_smi,
                            "transform": name,
                            "rationale": description,
                            "score": _score_for_objective(parent_props, child_props, objective),
                            "properties": child_props,
                            "property_deltas": _property_deltas(parent_props, child_props),
                            "lipinski_violations": _lipinski_violations(child_props),
                        })
                    except Exception:
                        continue
        except Exception:
            continue
    return suggestions


def _apply_simple_additions(
    mol, parent_props: dict, objective: str, seen_smiles: set, n_suggestions: int
) -> list[dict]:
    """Add a single atom (F/OH/NH2/Me) to an aromatic CH as a fallback modification."""
    from rdkit import Chem
    from rdkit.Chem import RWMol

    suggestions = []
    for add_name, add_atom, add_desc in _SIMPLE_ADDITIONS:
        if len(suggestions) >= n_suggestions * 3:
            break
        try:
            pattern = Chem.MolFromSmarts("[cH]")
            if not (pattern and mol.HasSubstructMatch(pattern)):
                continue
            matches = mol.GetSubstructMatches(pattern)
            if not matches:
                continue
            for match in matches[:1]:  # just first match
                rw = RWMol(mol)
                new_idx = rw.AddAtom(Chem.Atom(add_atom))
                rw.AddBond(match[0], new_idx, Chem.BondType.SINGLE)
                try:
                    Chem.SanitizeMol(rw)
                    new_smi = Chem.MolToSmiles(rw)
                    if new_smi in seen_smiles:
                        continue
                    seen_smiles.add(new_smi)

                    new_mol = Chem.MolFromSmiles(new_smi)
                    if new_mol is None:
                        continue

                    child_props = _compute_properties(new_mol)
                    suggestions.append({
                        "smiles": new_smi,
                        "transform": add_name,
                        "rationale": add_desc,
                        "score": _score_for_objective(parent_props, child_props, objective),
                        "properties": child_props,
                        "property_deltas": _property_deltas(parent_props, child_props),
                        "lipinski_violations": _lipinski_violations(child_props),
                    })
                except Exception:
                    continue
        except Exception:
            continue
    return suggestions
