"""Namespace construction for the sandbox exec() environment."""

from pathlib import Path
from typing import Any

from agent.sandbox.guards import configure_matplotlib, make_safe_import, make_safe_open, make_safe_subprocess


class SandboxSetupMixin:
    """Owns sandbox construction and the exec() namespace it exposes."""

    def __init__(self, timeout: int = 30, output_dir: Path = None, max_retries: int = 2,
                 extra_read_dirs: list[Path] = None):
        self.timeout = timeout
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "outputs"
        self.max_retries = max_retries
        self.extra_read_dirs = [Path(d).resolve() for d in (extra_read_dirs or [])]
        self._namespace: dict[str, Any] = {}
        self._setup_namespace()

    def _setup_namespace(self):
        """Populate namespace with safe libraries and utilities."""
        import collections
        import csv
        import datetime
        import glob as glob_mod
        import gzip
        import io
        import itertools
        import json
        import math
        import os.path
        import re
        import struct
        import tempfile
        import urllib.request
        import zipfile

        configure_matplotlib()
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd

        # Build safe builtins dict
        if isinstance(__builtins__, dict):
            safe_builtins = dict(__builtins__)
        else:
            safe_builtins = {k: getattr(__builtins__, k) for k in dir(__builtins__)}
        safe_builtins["__import__"] = make_safe_import(__import__)
        safe_builtins["open"] = make_safe_open(self.output_dir, self.extra_read_dirs)

        self._namespace = {
            # Core data science
            "pd": pd,
            "np": np,
            "plt": plt,
            "json": json,
            "re": re,
            "math": math,
            "collections": collections,
            "itertools": itertools,
            "datetime": datetime,
            "zipfile": zipfile,
            "glob": glob_mod,
            "io": io,
            "tempfile": tempfile,
            "struct": struct,
            "csv": csv,
            "gzip": gzip,
            "os": os,
            "os.path": os.path,
            "urllib": __import__("urllib"),
            "urllib.request": urllib.request,
            "Path": Path,
            # Output directory
            "OUTPUT_DIR": self.output_dir,
            # Safe import
            "__builtins__": safe_builtins,
        }

        # Add safe_subprocess_run for whitelisted bioinformatics tools
        self._namespace["safe_subprocess_run"] = make_safe_subprocess()

        # Optional libraries — add if available
        try:
            import scipy.stats as scipy_stats
            self._namespace["scipy_stats"] = scipy_stats
            self._namespace["scipy"] = __import__("scipy")
        except ImportError:
            pass

        try:
            import seaborn as sns
            self._namespace["sns"] = sns
        except ImportError:
            pass

        try:
            import sklearn
            self._namespace["sklearn"] = sklearn
        except ImportError:
            pass

        # rpy2 for R model fitting (when questions explicitly require R)
        try:
            import rpy2.robjects as ro
            self._namespace["ro"] = ro
            self._namespace["rpy2"] = __import__("rpy2")
        except ImportError:
            pass

        # Pre-built helper for parsimony informative sites (gap-correct)
        from collections import Counter as _Counter

        def compute_pi_percentage(seqs):
            """Compute parsimony informative site percentage. EXCLUDES gap characters.

            Only '-', 'X', and '*' are treated as gaps.
            'N' is NOT excluded (it's asparagine in protein alignments).
            '?' is NOT excluded (it may represent valid ambiguity).
            """
            if not seqs or len(seqs) < 2:
                return 0.0
            aln_len = len(seqs[0])
            pi_count = 0
            for i in range(aln_len):
                col = [s[i].upper() for s in seqs if i < len(s)]
                col = [c for c in col if c not in ('-', 'X', '*')]
                if len(col) < 2:
                    continue
                counts = _Counter(col)
                if sum(1 for c, n in counts.items() if n >= 2) >= 2:
                    pi_count += 1
            return pi_count / aln_len * 100

        self._namespace["compute_pi_percentage"] = compute_pi_percentage
