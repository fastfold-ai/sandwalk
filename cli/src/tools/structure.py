"""
Structure prediction tools: AlphaFold fetch, docking, MD simulation, FEP, binding sites.

ternary_predict and batch_screen require the TernaryPred sister project
(github.com/celltype/TernaryPred) to be installed locally. All other tools
work standalone.

Split across tools/structure_ternary.py (ternary_predict/batch_screen), tools/structure_fetch.py
(alphafold_fetch/compound_3d/_resolve_pdb), tools/structure_docking.py (dock),
tools/structure_md.py (md_simulate), tools/structure_fep.py (fep), and
tools/structure_binding_site.py (binding_site); re-exported here for backward
compatibility. This module is the canonical patch target for tests
(e.g. ``patch("tools.structure.subprocess")``); submodules access shared constants
and cross-cluster tools indirectly via ``from tools import structure as _structure``
so that such patches take effect regardless of which submodule performs the call.
"""

import json
import subprocess
import sys
from pathlib import Path

from agent.config import CONFIG_DIR
from tools import registry
from tools.http_client import request

TERNARYPRED_DIR = Path.home() / "Projects" / "CellType" / "TernaryPred"

from tools.structure_binding_site import _geometric_pocket_detection, binding_site
from tools.structure_docking import _detect_search_box, _prepare_ligand_pdbqt, dock
from tools.structure_fep import fep
from tools.structure_fetch import _resolve_pdb, alphafold_fetch, compound_3d
from tools.structure_md import md_simulate
from tools.structure_ternary import batch_screen, ternary_predict

__all__ = [
    "json",
    "subprocess",
    "sys",
    "Path",
    "CONFIG_DIR",
    "request",
    "TERNARYPRED_DIR",
    "ternary_predict",
    "batch_screen",
    "alphafold_fetch",
    "compound_3d",
    "_resolve_pdb",
    "_prepare_ligand_pdbqt",
    "_detect_search_box",
    "dock",
    "md_simulate",
    "fep",
    "_geometric_pocket_detection",
    "binding_site",
]
