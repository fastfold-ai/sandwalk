"""Slack's Agents & AI Apps container.

The container needs a paid workspace, so the behaviour that matters most is
what happens without one: everything must degrade to a no-op and leave
mention-based flow untouched.
"""

from __future__ import annotations

import asyncio

from agent_server.connectors.slack_assistant import (
    DEFAULT_PROMPTS,
    SlackAssistant,
    channel_ref,
    is_assistant_event,
    is_dm_opened,
    prompts_for,
    unsupported,
)


def run(coro):
    return asyncio.run(coro)


class FakeWeb:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, dict]] = []

    def __getattr__(self, name):
        async def call(**kwargs):
            self.calls.append((name, kwargs))
            if self.error:
                raise self.error
            return {"ok": True}

        return call


def assistant_with(error: Exception | None = None) -> tuple[SlackAssistant, FakeWeb]:
    assistant = SlackAssistant(bot_token="xoxb-x")
    web = FakeWeb(error)
    assistant._client = web
    return assistant, web


class TestEventRecognition:
    def test_spots_assistant_events(self):
        assert is_assistant_event({"type": "app_home_opened"})
        assert is_assistant_event({"type": "app_context_changed"})

    def test_ignores_ordinary_events(self):
        assert not is_assistant_event({"type": "app_mention"})
        assert not is_assistant_event({"type": "message"})
        assert not is_assistant_event(None)

    def test_dm_opened_requires_the_messages_tab(self):
        assert is_dm_opened({"type": "app_home_opened", "tab": "messages"})
        assert not is_dm_opened({"type": "app_home_opened", "tab": "home"})
        assert not is_dm_opened({"type": "app_context_changed", "tab": "messages"})
        assert not is_dm_opened(None)

    def test_reads_the_channel_reference(self):
        event = {"type": "app_home_opened", "tab": "messages", "channel": "D1"}
        assert channel_ref(event) == "D1"

    def test_missing_channel_reference(self):
        assert channel_ref({}) is None
        assert channel_ref(None) is None


class TestUnsupportedDetection:
    def test_recognises_a_workspace_that_cannot_host_assistants(self):
        for message in (
            "missing_scope",
            "assistant_not_enabled",
            "plan_upgrade_required",
            "not_allowed_token_type",
        ):
            assert unsupported(RuntimeError(message)), message

    def test_a_real_fault_is_not_mistaken_for_an_unsupported_plan(self):
        assert not unsupported(RuntimeError("ratelimited"))
        assert not unsupported(RuntimeError("connection reset"))


class TestStatus:
    def test_sets_the_thinking_indicator(self):
        assistant, web = assistant_with()
        assert run(assistant.set_status(channel_id="D1", thread_ts="1.1", status="x"))
        name, kwargs = web.calls[0]
        assert name == "assistant_threads_setStatus"
        assert kwargs["status"] == "x"

    def test_clearing_sends_an_empty_status(self):
        assistant, web = assistant_with()
        run(assistant.clear_status(channel_id="D1", thread_ts="1.1"))
        assert web.calls[0][1]["status"] == ""

    def test_needs_a_thread(self):
        assistant, web = assistant_with()
        assert not run(assistant.set_status(channel_id="", thread_ts="", status="x"))
        assert web.calls == []


class TestDegradation:
    def test_a_free_workspace_stops_trying(self):
        """One refusal is enough; do not pay for a failed call every turn."""
        assistant, web = assistant_with(RuntimeError("plan_upgrade_required"))

        assert not run(assistant.set_status(channel_id="D1", thread_ts="1.1", status="x"))
        assert assistant.supported is False

        assert not run(assistant.set_status(channel_id="D1", thread_ts="1.1", status="y"))
        assert len(web.calls) == 1, "should not have called Slack again"

    def test_a_transient_failure_does_not_latch(self):
        assistant, web = assistant_with(RuntimeError("ratelimited"))
        run(assistant.set_status(channel_id="D1", thread_ts="1.1", status="x"))
        assert assistant.supported is True
        run(assistant.set_status(channel_id="D1", thread_ts="1.1", status="y"))
        assert len(web.calls) == 2

    def test_failures_never_raise(self):
        assistant, _ = assistant_with(RuntimeError("boom"))
        assert not run(assistant.set_title(channel_id="D1", thread_ts="1.1", title="t"))
        assert not run(
            assistant.set_prompts(channel_id="D1", prompts=[{"title": "a", "message": "b"}])
        )


class TestPrompts:
    def test_defaults_without_specialists(self):
        assert prompts_for(None) == DEFAULT_PROMPTS
        assert prompts_for([]) == DEFAULT_PROMPTS

    def test_uses_specialist_names(self):
        prompts = prompts_for(["Biologist", "Chemist"])
        titles = [p["title"] for p in prompts]
        assert "Biologist" in titles and "Chemist" in titles

    def test_never_exceeds_slacks_limit_of_four(self):
        prompts = prompts_for([f"S{i}" for i in range(20)])
        assert len(prompts) <= 4

    def test_every_prompt_has_the_required_shape(self):
        for prompt in prompts_for(["One", "Two"]):
            assert set(prompt) == {"title", "message"}
            assert prompt["title"] and prompt["message"]

    def test_a_long_title_is_truncated_for_slack(self):
        assistant, web = assistant_with()
        run(assistant.set_title(channel_id="D1", thread_ts="1.1", title="z" * 500))
        assert len(web.calls[0][1]["title"]) <= 120

    def test_prompts_do_not_need_a_thread(self):
        """Agent-experience prompts sit above the composer, not inside a thread."""
        assistant, web = assistant_with()
        assert run(
            assistant.set_prompts(channel_id="D1", prompts=[{"title": "a", "message": "b"}])
        )
        name, kwargs = web.calls[0]
        assert name == "assistant_threads_setSuggestedPrompts"
        assert "thread_ts" not in kwargs

    def test_prompts_need_a_channel(self):
        assistant, web = assistant_with()
        assert not run(assistant.set_prompts(channel_id="", prompts=[{"title": "a", "message": "b"}]))
        assert web.calls == []
