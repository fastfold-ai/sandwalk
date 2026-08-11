"""_compound_resolver — part 1 of split module. See tools/_compound_resolver.py."""
from tools._compound_resolver_base import (
    _PROT_MAPPING_CSV,
    _SMILES_CSV,
    _prot_to_yu,
    _yu_smiles,
    _yu_to_prot,
    csv,
    lru_cache,
    os,
)


def _load_yu_smiles() -> dict:
    """Load YU compound → SMILES mapping (lazy, cached)."""
    global _yu_smiles
    if _yu_smiles is not None:
        return _yu_smiles
    _yu_smiles = {}
    if not os.path.exists(_SMILES_CSV):
        return _yu_smiles
    with open(_SMILES_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            _yu_smiles[row["compound"]] = row["smiles"]
    return _yu_smiles
def _load_prot_mapping() -> tuple[dict, dict]:
    """Load proteomics Cmpd ↔ YU mapping (lazy, cached)."""
    global _prot_to_yu, _yu_to_prot
    if _prot_to_yu is not None:
        return _prot_to_yu, _yu_to_prot
    _prot_to_yu = {}
    _yu_to_prot = {}
    if not os.path.exists(_PROT_MAPPING_CSV):
        return _prot_to_yu, _yu_to_prot
    with open(_PROT_MAPPING_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            _prot_to_yu[row["cmpd_id"]] = row["yu_id"]
            _yu_to_prot[row["yu_id"]] = row["cmpd_id"]
    return _prot_to_yu, _yu_to_prot
@lru_cache(maxsize=64)
def _tanimoto_search(smiles: str, candidate_ids: frozenset) -> tuple[str, float] | None:
    """Find most similar YU compound to a SMILES string by Tanimoto similarity."""
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem, DataStructs
    except ImportError:
        return None

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    query_fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)

    yu_smiles = _load_yu_smiles()
    best_id, best_sim = None, 0.0

    for yu_id in candidate_ids:
        smi = yu_smiles.get(yu_id)
        if not smi:
            continue
        m = Chem.MolFromSmiles(smi)
        if m is None:
            continue
        fp = AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048)
        sim = DataStructs.TanimotoSimilarity(query_fp, fp)
        if sim > best_sim:
            best_sim = sim
            best_id = yu_id

    if best_id is None:
        return None
    return best_id, round(best_sim, 4)
