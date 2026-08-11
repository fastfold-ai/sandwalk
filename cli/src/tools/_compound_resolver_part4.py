"""_compound_resolver — part 4 of split module. See tools/_compound_resolver.py."""
from tools._compound_resolver_part1 import _load_prot_mapping

def _get_dataset_compounds(dataset: str) -> set:
    """Get the set of YU compound IDs available in a dataset."""
    try:
        if dataset == "prism":
            from data.loaders import load_prism
            prism = load_prism()
            return set(prism["pert_name"].unique())
        elif dataset == "l1000":
            from data.loaders import load_l1000
            l1000 = load_l1000()
            return set(l1000.index.tolist())
        elif dataset == "proteomics":
            _, yu_to_prot = _load_prot_mapping()
            return set(yu_to_prot.keys())
    except (FileNotFoundError, ImportError):
        pass
    return set()
