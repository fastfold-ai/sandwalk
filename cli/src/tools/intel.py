"""intel: split into tools/intel_base.py + tools/intel_part*.py."""
from __future__ import annotations

from tools.intel_part1 import (
    _to_int,
    pipeline_watch,
)
from tools.intel_part2 import (
    competitor_snapshot,
)
