"""Slack's Agents & AI Apps container.

Gives Sandwalk a dedicated assistant surface rather than only channel mentions:
a native "is thinking" indicator, suggested prompts when a thread opens, and a
thread title. It arrives over the same relay as everything else, since these
are ordinary Events API events.

Two constraints shape this. The container requires a paid Slack workspace, so
everything here must no-op cleanly when Slack refuses - mention-based flow has
to keep working regardless. And ``assistant.threads.setStatus`` only applies to
assistant threads, so channel mentions keep the reaction-based progress signal
rather than being migrated.

Slack's Agent messaging experience (``agent_view``) is what new apps get - the
older Assistant messaging experience (``assistant_view``) is being phased out
and cannot even be selected for a new app. It changes the event shape: there is
no ``assistant_thread_started`` any more, so opening the DM is detected from an
ordinary ``app_home_opened`` event instead, and the API calls below no longer
need a ``thread_ts`` (Agent-experience threads are just message groups, not a
separate container the user opens first). See
https://docs.slack.dev/ai/developing-agents/#migrating.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("agent_server.connectors.slack")

ASSISTANT_EVENTS = frozenset({"app_home_opened", "app_context_changed"})

# Shown while the agent works. Slack clears it automatically once the app
# replies, and expires it after roughly two minutes if nothing arrives.
THINKING_STATUS = "is thinking..."

# Errors meaning "this workspace cannot do assistants", as opposed to a real
# fault. Free plans and apps without the feature enabled land here.
_UNSUPPORTED = (
    "not_allowed_token_type",
    "missing_scope",
    "assistant_not_enabled",
    "feature_not_enabled",
    "plan_upgrade_required",
)

DEFAULT_PROMPTS = [
    {"title": "Fold a protein", "message": "Fold this sequence and report pLDDT."},
    {"title": "Check a target", "message": "What is known about this target?"},
    {"title": "Analyse data", "message": "Help me analyse an experiment."},
]


def is_assistant_event(event: dict) -> bool:
    return isinstance(event, dict) and str(event.get("type") or "") in ASSISTANT_EVENTS


def is_dm_opened(event: dict) -> bool:
    """Whether this is the Agent-experience signal for "user opened the DM".

    Replaces ``assistant_thread_started``, which no longer fires under
    ``agent_view``. ``app_home_opened`` fires for other tabs too, so it only
    counts when ``tab`` is ``"messages"``.
    """
    return (
        isinstance(event, dict)
        and str(event.get("type") or "") == "app_home_opened"
        and str(event.get("tab") or "") == "messages"
    )


def unsupported(exc: Exception) -> bool:
    """Whether Slack is saying the workspace cannot host an assistant."""
    text = str(exc).lower()
    return any(marker in text for marker in _UNSUPPORTED)


def channel_ref(event: dict) -> str | None:
    """DM channel id for an app_home_opened / app_context_changed event."""
    if not isinstance(event, dict):
        return None
    return str(event.get("channel") or "").strip() or None


def prompts_for(specialist_names: list[str] | None = None) -> list[dict]:
    """Starter prompts, drawn from the user's specialists when there are any.

    Slack accepts at most four, and shows them only on a fresh thread.
    """
    if not specialist_names:
        return list(DEFAULT_PROMPTS)
    prompts = [
        {"title": name, "message": f"Work on this as {name}."}
        for name in specialist_names[:3]
    ]
    prompts.append(DEFAULT_PROMPTS[0])
    return prompts[:4]


class SlackAssistant:
    """Thin wrapper over the assistant Web API calls, safe on any plan."""

    def __init__(self, *, bot_token: str) -> None:
        self.bot_token = bot_token
        self._client = None
        # Latches once Slack says the workspace cannot do this, so a free plan
        # does not pay for a failed API call on every single turn.
        self.supported = True

    def _web(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            from slack_sdk.web.async_client import AsyncWebClient

            self._client = AsyncWebClient(
                token=self.bot_token,
                base_url=os.environ.get("SLACK_API_URL", "https://slack.com/api/"),
            )
        return self._client

    async def _call(self, name: str, **kwargs) -> bool:  # type: ignore[no-untyped-def]
        if not self.supported:
            return False
        try:
            await getattr(self._web(), name)(**kwargs)
            return True
        except Exception as exc:  # noqa: BLE001
            if unsupported(exc):
                self.supported = False
                logger.info(
                    "Slack assistant features unavailable for this workspace (%s); "
                    "mentions continue to work",
                    exc,
                )
            else:
                logger.debug("Slack %s failed: %s", name, exc)
            return False

    async def set_status(self, *, channel_id: str, thread_ts: str, status: str) -> bool:
        """Show or clear the native thinking indicator."""
        if not channel_id or not thread_ts:
            return False
        return await self._call(
            "assistant_threads_setStatus",
            channel_id=channel_id,
            thread_ts=thread_ts,
            status=status,
        )

    async def clear_status(self, *, channel_id: str, thread_ts: str) -> bool:
        return await self.set_status(channel_id=channel_id, thread_ts=thread_ts, status="")

    async def set_title(self, *, channel_id: str, thread_ts: str, title: str) -> bool:
        if not title:
            return False
        return await self._call(
            "assistant_threads_setTitle",
            channel_id=channel_id,
            thread_ts=thread_ts,
            title=title[:120],
        )

    async def set_prompts(
        self, *, channel_id: str, thread_ts: str | None = None, prompts: list[dict]
    ) -> bool:
        """Show starter prompts. Under agent_view these sit atop the Messages
        tab rather than inside a thread, so ``thread_ts`` is optional - Slack's
        own docs say it "is not needed" in the Agent messaging experience.
        """
        if not prompts or not channel_id:
            return False
        kwargs: dict = {"channel_id": channel_id, "prompts": prompts}
        if thread_ts:
            kwargs["thread_ts"] = thread_ts
        return await self._call("assistant_threads_setSuggestedPrompts", **kwargs)
