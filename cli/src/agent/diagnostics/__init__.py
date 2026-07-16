"""Build a shareable diagnostics zip for support (Operon-style).

Includes system info, doctor report, redacted config, and recent log files.
Excludes conversations and credential values.

Split into `redact.py` (secret/path redaction), `logging_setup.py`
(file logging + uvicorn log config), `collectors.py` (system/config/skills/
log collectors), and `zipper.py` (build_diagnostics_zip) to stay under the
file-length cap; re-exported here so `from agent.diagnostics import ...`
keeps working unchanged.
"""

from .logging_setup import LOGS_DIR, ensure_logging_configured, uvicorn_log_config
from .redact import _HOME, _redact_obj, _redact_text
from .zipper import build_diagnostics_zip

__all__ = [
    "LOGS_DIR",
    "build_diagnostics_zip",
    "ensure_logging_configured",
    "uvicorn_log_config",
]
