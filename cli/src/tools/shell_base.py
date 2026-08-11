"""
Shell execution tool for ct.

Run shell commands from within ct research workflows with safety restrictions.
"""

import os
import re
import shlex
import subprocess
from pathlib import Path

from tools import registry

# Expand $VAR / ${VAR} in argv when shell=False (subprocess does not).
_ENV_VAR_PATTERN = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
