"""Shared Enter-to-accept logic for / # @ completions."""

from __future__ import annotations


def _completion_text(completion) -> str:
    return str(getattr(completion, "text", "") or "")


def accept_file_completion(buffer) -> bool:
    """If ``@`` file completions are open, insert the chip and stay in the input.

    Returns True when Enter was handled (do not submit).
    """
    cs = getattr(buffer, "complete_state", None)
    completions = getattr(cs, "completions", None) if cs is not None else None
    if not cs or not completions:
        return False
    # File chips always start with ``@[`` (keeps the @ trigger on the chip).
    sample = completions[0]
    if not _completion_text(sample).startswith("@["):
        return False
    if cs.complete_index is None:
        buffer.go_to_completion(0)
        cs = buffer.complete_state
    if cs and cs.current_completion:
        buffer.apply_completion(cs.current_completion)
    # Space after the chip so the user can keep typing around it.
    try:
        after = buffer.document.text_after_cursor or ""
    except Exception:  # noqa: BLE001
        after = ""
    if not after or not after[0].isspace():
        buffer.insert_text(" ")
    buffer.cancel_completion()
    return True


def accept_slash_completion(buffer) -> bool:
    """Apply the current/first ``/`` completion. Returns True if applied."""
    cs = getattr(buffer, "complete_state", None)
    completions = getattr(cs, "completions", None) if cs is not None else None
    if not cs or not completions:
        return False
    # Slash menu entries always start with ``/``.
    if not _completion_text(completions[0]).startswith("/"):
        return False
    if cs.complete_index is None:
        buffer.go_to_completion(0)
        cs = buffer.complete_state
    if cs and cs.current_completion:
        buffer.apply_completion(cs.current_completion)
        return True
    return False
