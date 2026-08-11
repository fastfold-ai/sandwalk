"""In-memory OAuth PKCE state (local agent server only)."""

from __future__ import annotations

import threading
from typing import Any

_oauth_states: dict[str, dict[str, Any]] = {}
_oauth_lock = threading.Lock()
