"""sandwalk CLI entry point.

Usage:
    sandwalk                              # Interactive mode
    sandwalk "your question"              # Single query
    sandwalk --smiles "CCO" "Profile"     # With compound context
    sandwalk config set key value         # Configuration
    sandwalk data pull depmap             # Data management

This package is a thin composition root: each command group lives in its own
module under ``cli/`` (or ``cli/setup/``) and is imported below purely for its
side effect of registering commands on the shared Typer ``app``. ``cli/_compat.py``
and ``cli/setup/_compat.py`` restore the flat namespace the single ``cli.py``
module used to provide (needed for tests/scripts that import helpers directly
off ``cli``, and so stdlib-singleton monkeypatches like ``cli.subprocess.run``
keep working).
"""
# ruff: noqa: I001 — hand-packed imports (kept compact to fit the line-count cap)

import os
import random
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

from cli.app import app, console, spinner
from cli.main import entry

# Import every command-group module so their @app.command / add_typer calls run.
from cli import (  # noqa: F401
    auth, bench, case_study, config, data, doctor, fork, knowledge,
    knowledge_quality, mcp, release_check, report, report_notebook, run,
    sandbox, serve, skills, skills_manage, specialists, sync, tool, trace,
    trace_export, upgrade,
)
from cli.setup import wizard as setup_wizard  # noqa: F401

# Backward-compatible flat re-exports (see module docstrings for why).
from cli._compat import *  # noqa: F401,F403
from cli.setup._compat import *  # noqa: F401,F403

__all__ = ["app", "entry"]


if __name__ == "__main__":
    entry()
