"""Shared marker panels and scanpy availability check for single-cell tools.

Split from tools/singlecell.py.
"""

from __future__ import annotations

# Canonical marker gene panels for common cell types
MARKER_PANELS = {
    "T cells": ["CD3D", "CD3E", "CD3G", "CD2", "TRAC"],
    "CD4+ T cells": ["CD4", "IL7R", "CCR7", "LEF1"],
    "CD8+ T cells": ["CD8A", "CD8B", "GZMK", "GZMB"],
    "Regulatory T cells": ["FOXP3", "IL2RA", "CTLA4", "TIGIT"],
    "B cells": ["CD79A", "CD79B", "MS4A1", "CD19", "PAX5"],
    "Plasma cells": ["JCHAIN", "MZB1", "SDC1", "XBP1"],
    "NK cells": ["NKG7", "GNLY", "KLRD1", "KLRF1", "NCAM1"],
    "Monocytes": ["LYZ", "S100A8", "S100A9", "CD14", "FCGR3A"],
    "Macrophages": ["CD68", "CD163", "MRC1", "MSR1", "MARCO"],
    "Dendritic cells": ["FCER1A", "CLEC10A", "CD1C", "ITGAX"],
    "Plasmacytoid DCs": ["LILRA4", "IRF7", "TCF4", "CLEC4C"],
    "Neutrophils": ["CSF3R", "FCGR3B", "CXCR2", "S100A12"],
    "Mast cells": ["KIT", "TPSAB1", "TPSB2", "CPA3"],
    "Erythrocytes": ["HBA1", "HBA2", "HBB", "GYPA"],
    "Platelets": ["PPBP", "PF4", "GP9", "ITGA2B"],
    "Fibroblasts": ["DCN", "COL1A1", "COL1A2", "LUM", "PDGFRA"],
    "Endothelial": ["PECAM1", "VWF", "CDH5", "ERG", "FLT1"],
    "Epithelial": ["EPCAM", "KRT18", "KRT19", "CDH1"],
}


def _check_scanpy():
    """Check if scanpy is installed and return it, or None."""
    try:
        import scanpy as sc
        return sc
    except ImportError:
        return None
