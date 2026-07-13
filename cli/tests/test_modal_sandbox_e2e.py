"""Gated live Modal sandbox E2E — skipped without MODAL_TOKEN_*."""

from __future__ import annotations

import os

import pytest

from agent.sandbox_probe import run_modal_sandbox_probe

_HAS_TOKENS = bool(
    os.environ.get("MODAL_TOKEN_ID", "").strip()
    and os.environ.get("MODAL_TOKEN_SECRET", "").strip()
)


pytestmark = [
    pytest.mark.modal_e2e,
    pytest.mark.skipif(
        not _HAS_TOKENS,
        reason="Set MODAL_TOKEN_ID and MODAL_TOKEN_SECRET to run live Modal E2E",
    ),
]


def test_modal_sandbox_probe_live():
    report = run_modal_sandbox_probe(terminate=True)
    assert not report.skipped
    assert report.ok, report.to_dict()
