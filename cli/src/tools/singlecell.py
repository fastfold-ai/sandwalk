"""
Single-cell analysis tools: clustering, trajectory inference, cell type annotation.

Requires scanpy for computation. Gracefully returns install instructions if missing.

Split across tools/singlecell_common.py (MARKER_PANELS/_check_scanpy),
tools/singlecell_cluster.py (cluster), tools/singlecell_trajectory.py
(trajectory), and tools/singlecell_annotate.py (cell_type_annotate);
re-exported here for backward compatibility. This module is the canonical
patch target for tests (e.g. ``patch("tools.singlecell._check_scanpy")``);
submodules access ``_check_scanpy``/``MARKER_PANELS`` indirectly via
``from tools import singlecell as _singlecell`` so that such patches take
effect regardless of which submodule performs the call.
"""

from __future__ import annotations

from tools.singlecell_annotate import cell_type_annotate
from tools.singlecell_cluster import cluster
from tools.singlecell_common import _check_scanpy, MARKER_PANELS
from tools.singlecell_trajectory import trajectory

__all__ = [
    "MARKER_PANELS",
    "_check_scanpy",
    "cluster",
    "trajectory",
    "cell_type_annotate",
]
