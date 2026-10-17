"""Bench checklist heuristics and the JSON judge parser."""

from __future__ import annotations

from types import SimpleNamespace

from agent_server.bench_service import judge


def test_heuristic_checklist_matches_tools_and_prefixes():
    result = judge.heuristic_checklist(
        ["chem.search", "fold.run"],
        [
            {"id": "search", "require_tools": ["chem.search"]},
            {"id": "any-fold", "require_tools": ["fold.*"]},
            {"id": "missing", "require_tools": ["dock"]},
            {"id": "judged", "judge": True, "require_tools": ["chem.search"]},
            {"id": ""},
            {"require_tools": []},
        ],
    )
    assert result == {"search": True, "any-fold": True, "missing": False}


def test_collect_tool_names_from_events():
    names = judge.collect_tool_names_from_events(
        [
            {"type": "tool.started", "payload": {"name": "chem.search"}},
            SimpleNamespace(type="tool.completed", payload={"tool": "fold.run"}),
            {"type": "text", "payload": {"name": "ignored"}},
            "not-an-event",
        ]
    )
    assert names == ["chem.search", "fold.run"]


def test_parse_judge_json():
    parsed = judge._parse_judge_json('note {"overall_pass": true, "items": []}')
    assert parsed["overall_pass"] is True
    assert judge._parse_judge_json("no json")["overall_pass"] is False
    assert judge._parse_judge_json("{")["raw"]
    assert judge._parse_judge_json("[1]")["overall_pass"] is False


def test_run_llm_judge_reads_a_model_reply(monkeypatch):
    class _Model:
        def invoke(self, prompt):
            assert "Rubric" in prompt
            return SimpleNamespace(content=[{"text": '{"overall_pass": true, "items": []}'}])

    monkeypatch.setattr(judge, "logger", judge.logger)
    monkeypatch.setattr(
        "agent.config.Config.load",
        lambda: object(),
        raising=False,
    )

    def _build(config):
        return _Model()

    import agent.deepagents_runtime.chat_model as chat_model

    monkeypatch.setattr(chat_model, "build_chat_model", _build)
    # run_llm_judge imports inside the function.
    import agent.config as agent_config

    monkeypatch.setattr(agent_config.Config, "load", staticmethod(lambda: object()))
    result = judge.run_llm_judge(evidence="did the thing", ideal="42", rubric=None)
    assert result["overall_pass"] is True


def test_run_llm_judge_reports_a_failed_call(monkeypatch):
    class _Model:
        def invoke(self, prompt):
            raise RuntimeError("boom")

    import agent.config as agent_config
    import agent.deepagents_runtime.chat_model as chat_model

    monkeypatch.setattr(agent_config.Config, "load", staticmethod(lambda: object()))
    monkeypatch.setattr(chat_model, "build_chat_model", lambda config: _Model())
    result = judge.run_llm_judge(
        evidence="x",
        ideal=None,
        rubric=None,
        checklist=[{"id": "a", "description": "did it"}],
    )
    assert result["overall_pass"] is False
    assert "boom" in result["error"]
