"""Modal token presence check."""

from __future__ import annotations

import os
from typing import Any


def modal_tokens_present(config: Any | None = None) -> tuple[bool, str]:
    from agent.config import Config, sync_process_env_from_config

    cfg = config or Config.load()
    sync_process_env_from_config(
        cfg,
        only_missing=False,
        config_keys=["compute.modal_token_id", "compute.modal_token_secret"],
    )
    token_id = (os.environ.get("MODAL_TOKEN_ID") or "").strip()
    token_secret = (os.environ.get("MODAL_TOKEN_SECRET") or "").strip()
    if token_id and token_secret:
        return True, "MODAL_TOKEN_ID and MODAL_TOKEN_SECRET are set"
    return False, "Missing MODAL_TOKEN_ID and/or MODAL_TOKEN_SECRET"
