"""Pure bench row builders and session activity timestamps."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from agent_server.bench_service import spawn_core as sc


def test_iso_epoch_accepts_numbers_and_iso_text():
    assert sc._iso_epoch(None) == 0.0
    assert sc._iso_epoch("") == 0.0
    assert sc._iso_epoch(12) == 12.0
    stamp = datetime(2026, 10, 17, tzinfo=UTC).isoformat().replace("+00:00", "Z")
    assert sc._iso_epoch(stamp) > 0
    assert sc._iso_epoch("not-a-date") == 0.0


def test_session_activity_uses_messages_then_events():
    session = SimpleNamespace(
        id="s1",
        last_message_at=10,
        updated_at=4,
    )
    assert sc._session_activity_epoch(SimpleNamespace(), session) == 10.0

    class _Store:
        def list_events(self, session_id):
            assert session_id == "s1"
            return [
                SimpleNamespace(timestamp=3),
                SimpleNamespace(timestamp=40),
            ]

    assert sc._session_activity_epoch(_Store(), session) == 40.0

    class _Broken:
        def list_events(self, session_id):
            raise RuntimeError("closed")

    assert sc._session_activity_epoch(_Broken(), session) == 10.0


def test_skipped_and_failed_rows():
    question = SimpleNamespace(
        ideal="A",
        question="What?",
        focus="chem",
        id="q1",
        eval_mode="mcq",
    )
    cell = SimpleNamespace(question=question, prompt="prompt", question_id="q1")
    skipped = sc._skipped_question_row(
        {
            "cell": cell,
            "reason": "no mcp",
            "missing_skills": ["fold"],
            "missing_mcps": ["pymol"],
        },
        index=2,
    )
    assert skipped["skipped"] is True
    assert skipped["skip_reason"] == "no mcp"
    assert skipped["missing_skills"] == ["fold"]
    assert skipped["expected"] == "A"
    assert skipped["category"] == "chem"

    bare = SimpleNamespace(question=None, prompt="plain prompt", question_id="q2")
    failed = sc._failed_cell_row(bare, index=1, error="timeout")
    assert failed["eval_mode"] == "error"
    assert failed["judge"] == {"error": "timeout"}
    assert failed["question"] == "plain prompt"
    assert failed["category"] == "q2"
