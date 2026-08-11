"""Known local dataset/workflow catalog used by @ mention resolution."""

from __future__ import annotations

DATASET_CANDIDATES = [
    ("depmap", "dataset", "DepMap CRISPR/model data"),
    ("prism", "dataset", "PRISM drug sensitivity"),
    ("l1000", "dataset", "L1000 gene expression signatures"),
    ("proteomics", "dataset", "Proteomics log2FC matrix"),
    ("msigdb", "dataset", "MSigDB gene sets"),
    ("string", "dataset", "STRING protein interaction network"),
]

KNOWN_DATASETS = frozenset(d[0] for d in DATASET_CANDIDATES)


def _get_workflow_names() -> frozenset[str]:
    """Lazily load workflow names."""
    try:
        from agent.workflows import WORKFLOWS
        return frozenset(WORKFLOWS.keys())
    except Exception:
        return frozenset()
