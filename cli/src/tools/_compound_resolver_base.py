"""Compound name resolver — maps drug names to dataset-specific IDs.

The ct datasets use proprietary compound IDs:
- PRISM/L1000: YU-codes (e.g., YU254653)
- Proteomics: Cmpd format (e.g., Cmpd18_B10)

This module resolves common drug names (lenalidomide, pomalidomide, etc.)
to the most structurally similar compound in each dataset via Tanimoto similarity.
"""

import csv
import os
import re
from functools import lru_cache

# Data file paths
_DATA_DIR = "/mnt2/bronze/molecular_glue/crews_library"
_SMILES_CSV = os.path.join(_DATA_DIR, "all_compounds_smiles.csv")
_PROT_MAPPING_CSV = os.path.join(_DATA_DIR, "proteomics_to_yu_mapping.csv")

# Regex patterns
_YU_PATTERN = re.compile(r"^YU\d{6}$")
_CMPD_PATTERN = re.compile(r"^Cmpd\d+")

# Module-level caches (populated on first use)
_yu_smiles: dict | None = None
_prot_to_yu: dict | None = None
_yu_to_prot: dict | None = None
