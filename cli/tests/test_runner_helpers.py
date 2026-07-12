"""Tests for agent.runner pure helper functions."""

from agent.runner import (
    _extract_task_output_paths_from_text,
    _looks_like_unverified_execution_claim,
    _parse_task_probe_json,
)


class TestExecutionClaimDetection:
    def test_no_tools_with_submit_claim(self):
        summary = "I successfully submitted fold job fold_abc123def456"
        assert _looks_like_unverified_execution_claim(summary, []) is True

    def test_with_tool_calls_not_flagged(self):
        summary = "Job fold_abc123 is running"
        assert _looks_like_unverified_execution_claim(summary, [{"tool": "fold"}]) is False

    def test_benign_summary(self):
        assert _looks_like_unverified_execution_claim("TP53 is a tumor suppressor.", []) is False

    def test_empty_summary_not_flagged(self):
        assert _looks_like_unverified_execution_claim("   ", []) is False

    def test_submit_claim_without_generated_id_is_flagged(self):
        summary = "I created a job for your sequence and it is queued."
        assert _looks_like_unverified_execution_claim(summary, []) is True

    def test_running_claim_without_tools_is_flagged(self):
        summary = "The workflow is running with your inputs now."
        assert _looks_like_unverified_execution_claim(summary, []) is True


class TestTaskHelpers:
    def test_extract_task_output_paths(self):
        text = ["See output at /home/user/tasks/task_abc.output for details."]
        paths = _extract_task_output_paths_from_text(text)
        assert paths["task_abc"] == "/home/user/tasks/task_abc.output"

    def test_parse_task_probe_json(self):
        raw = '{"task_abc": "completed", "task_def": "running"}'
        parsed = _parse_task_probe_json(raw)
        assert parsed["task_abc"] == "completed"
        assert parsed["task_def"] == "running"

    def test_parse_task_probe_json_empty(self):
        assert _parse_task_probe_json("") == {}
