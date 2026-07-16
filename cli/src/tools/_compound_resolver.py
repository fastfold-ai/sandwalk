"""_compound_resolver: split into tools/_compound_resolver_base.py + tools/_compound_resolver_part*.py."""
from tools._compound_resolver_part1 import (
    _load_prot_mapping,
    _load_yu_smiles,
    _tanimoto_search,
)
from tools._compound_resolver_part2 import (
    resolve_to_smiles,
)
from tools._compound_resolver_part3 import (
    _yu_to_proteomics_col,
    resolve_compound,
    resolve_proteomics_id,
)
from tools._compound_resolver_part4 import (
    _get_dataset_compounds,
)
