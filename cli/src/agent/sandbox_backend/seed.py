"""Push the local session workspace into a Modal sandbox and wait for it."""

from __future__ import annotations

import logging
import time

from agent.sandbox_backend.handle import SandboxHandle
from agent.sandbox_backend.provisioning import _seed_lock_for
from agent.sandbox_sync import WORKSPACE_REMOTE_ROOT, push_tree

logger = logging.getLogger(__name__)


def _seed_modal_workspace(handle: SandboxHandle) -> None:
    """Push local session workspace into Modal. Never uploads skills."""
    if handle.kind != "modal":
        return
    with _seed_lock_for(handle.session_id):
        if handle.seeded:
            return
        target = getattr(handle.backend, "default", handle.backend)
        try:
            try:
                target.execute(
                    f"mkdir -p {WORKSPACE_REMOTE_ROOT}",
                    timeout=60,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Modal mkdir failed: %s", exc)
            push_tree(target, handle.workspace_root)
        except Exception as exc:  # noqa: BLE001
            # Mark seeded anyway so a failed/partial sync does not retry forever.
            logger.warning("Modal workspace sync failed: %s", exc)
        finally:
            handle.seeded = True


def wait_until_seeded(
    handle: SandboxHandle,
    *,
    timeout: float = 120.0,
    poll_interval: float = 0.25,
) -> bool:
    """Block until Modal workspace seed finishes (or ``timeout`` elapses).

    Returns True when ``handle.seeded`` is True. Built-in handles always return
    True immediately. Used by the agent runner so the first Modal ``execute``
    sees a synced ``/workspace``.
    """
    if handle.kind != "modal":
        return True
    if handle.seeded:
        return True
    deadline = time.monotonic() + max(0.0, float(timeout))
    while not handle.seeded:
        if time.monotonic() >= deadline:
            logger.warning(
                "Timed out waiting for Modal workspace seed (session=%s)",
                handle.session_id,
            )
            return False
        time.sleep(max(0.05, float(poll_interval)))
    return True
