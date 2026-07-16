"""
L1000/CMap compound signature and connectivity tools.

Uses local L1000 Level 5 compound profiles (19,811 compounds × 978 landmark genes)
built from the Broad LINCS GSE92742 dataset. Falls back to CLUE API if configured.
"""

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from agent.config import Config
from tools import registry
