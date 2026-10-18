"""Deep Agents prompt assembly and result merge without a live model."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from agent.runner.deepagents_build import DeepAgentsBuildMixin, _empty_output_summary
from agent.runner.deepagents_run import DeepAgentsRunMixin, _merge_deepagents_chunks


class _Config:
    def __init__(self, values=None, setup=""):
        self.values = values or {}
        self.setup = setup

    def get(self, key, default=None):
        return self.values.get(key, default)

    def model_setup_message(self):
        if self.setup == "boom":
            raise RuntimeError("setup")
        return self.setup


class _Builder(DeepAgentsBuildMixin):
    def __init__(self, tmp_path):
        self.trajectory = SimpleNamespace(session_id="sess-1")
        self.session = SimpleNamespace(config=_Config({"agent.plan_preview": False, "agent.file_access": "workspace"}))
        self.trace_store = None
        self._headless = True
        self.tmp_path = tmp_path

    def _print_usage(self, *args, **kwargs):
        self.printed = True


def test_empty_summary_and_chunk_merge():
    assert _empty_output_summary(None).startswith("(Agent produced")
    assert "stop_reason" not in _empty_output_summary([{"stop_reason": ""}])
    text = _empty_output_summary([{"stop_reason": "refusal", "content_blocks": ["text", ""]}])
    assert "refusal" in text and "text" in text
    merged = _merge_deepagents_chunks(
        {"token_usage": {"input_tokens": 2}, "full_text": ["a"], "tool_calls": [], "model_call_count": 1, "empty_model_turns": []},
        {"token_usage": {"input_tokens": "nope", "output_tokens": 3}, "full_text": ["b"], "tool_calls": [{"name": "read"}], "model_call_count": 1, "empty_model_turns": [{}]},
    )
    assert merged["token_usage"]["input_tokens"] == "nope"
    assert merged["token_usage"]["output_tokens"] == 3
    assert merged["full_text"] == ["a", "b"]
    assert merged["model_call_count"] == 2


def test_user_prompt_and_exec_result(tmp_path, monkeypatch):
    host = _Builder(tmp_path)
    prompt, ctx = host._build_deepagents_user_prompt("hi", {"capy_mode": True})
    assert prompt == "hi" and ctx["capy_mode"] is True

    workspace = tmp_path / "ws"
    monkeypatch.setattr("agent.skills.mentions.build_skill_mention_context", lambda *a, **k: "skill ctx")
    monkeypatch.setattr("agent.mcp_manage.mentions.build_mcp_mention_context", lambda *a, **k: "")
    monkeypatch.setattr("agent.system_prompt.mode_section.list_recent_plan_files", lambda path: ["plan.md"])
    monkeypatch.setattr("agent.config.sync_process_env_from_config", lambda config: None)
    built, updated = host._build_deepagents_user_prompt(
        "design a binder",
        {
            "workspace_path": str(workspace),
            "compound_smiles": "CCO",
            "target": "EGFR",
            "indication": "cancer",
            "mention_context": "from the other chat",
            "allowed_skill_names": [],
            "mcp_servers": [],
        },
    )
    assert "EGFR" in built
    assert "skill ctx" in built
    assert (workspace / "plans").is_dir()
    assert updated["workspace_path"] == str(workspace)

    monkeypatch.setattr(
        "agent.runner.deepagents_build._looks_like_unverified_execution_claim",
        lambda summary, tool_calls: True,
    )
    claimed = host._build_deepagents_exec_result(
        "submit",
        {"full_text": ["submitted job 1"], "tool_calls": [], "token_usage": {}, "model_call_count": 1},
        0.0,
        "gpt",
        None,
        [],
        {},
    )
    assert "did not execute" in claimed.summary

    monkeypatch.setattr(
        "agent.runner.deepagents_build._looks_like_unverified_execution_claim",
        lambda summary, tool_calls: False,
    )
    monkeypatch.setattr(
        "agent.local_artifact_paths.append_downloaded_artifacts_block",
        lambda summary, paths: summary + " paths",
    )
    monkeypatch.setattr(
        "agent.local_artifact_paths.collect_paths_from_tool_calls",
        lambda calls: ["/tmp/a"],
    )
    sandbox = SimpleNamespace(get_variable=lambda name: {"answer": 7})
    host.trace_store = SimpleNamespace(
        add_events=lambda *a, **k: None,
        flush=lambda: (_ for _ in ()).throw(RuntimeError("disk")),
    )

    def _flush():
        raise RuntimeError("disk")

    host.trace_store.flush = _flush
    host._headless = False
    done = host._build_deepagents_exec_result(
        "fetch",
        {
            "full_text": ["saved"],
            "tool_calls": [{"name": "write", "input": {"path": "a"}}],
            "token_usage": {"input_tokens": 1000, "output_tokens": 500},
            "model_call_count": 2,
            "empty_model_turns": [],
        },
        0.0,
        "gpt",
        sandbox,
        [{"type": "tool"}],
        {"gpt": {"input": 1.0, "output": 2.0}},
    )
    assert done.raw_results["answer"] == 7
    assert done.metadata["sdk_cost_split_known"] is True
    assert host.printed is True
    assert "paths" in done.summary


def test_run_dispatch(monkeypatch):
    class _Runner(DeepAgentsRunMixin):
        def __init__(self, provider="nope", setup=""):
            self.session = SimpleNamespace(config=_Config({"llm.provider": provider}, setup))

        def _make_error_result(self, query, message, elapsed, prefix_sdk=True):
            return message

        async def _run_async_deepagents(self, query, context, progress_callback):
            return "ran"

    unknown = asyncio.run(_Runner()._run_async("q"))
    assert "Unsupported" in unknown
    setup = asyncio.run(_Runner(provider="openai", setup="Add a key in Models.")._run_async("q"))
    assert "Add a key" in setup
    healed = asyncio.run(_Runner(provider="openai", setup="boom")._run_async("q"))
    assert healed == "ran"
