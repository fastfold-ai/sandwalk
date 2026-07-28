"""How a Slack message is presented to the agent.

The agent sees who is speaking, where, and the exact reply handle to pass back to
``slack.send_message``. Keeping this in one place means the relay and Socket Mode
paths produce identical transcripts.
"""

from __future__ import annotations

from agent_server.connectors.gateway import InboundMessage

# Long channel titles make the session list unreadable.
_MAX_TITLE = 60


def frame_inbound(
    message: InboundMessage,
    *,
    channel_label: str,
    first_message: bool = False,
) -> str:
    """Wrap the raw Slack text with its origin and reply handle.

    Every Slack-sourced turn (mentions, DMs, thread follow-ups, and Listening
    subscriptions) must reply through ``slack.send_message``. ``first_message``
    is kept for callers/tests but no longer changes the instruction — Listening
    deliveries used to omit it and agents answered only in Sandwalk.
    """
    del first_message  # Reserved for callers; framing is consistent for all paths.
    who = message.user_name or message.user_id
    header = f"[Slack · {channel_label} | from {who} | reply→{message.thread_target}]"
    body = message.text.strip()
    return (
        f"{header}\n{body}\n\n"
        "You are answering in Slack. When you have the answer, call "
        f"`slack.send_message` with target `{message.thread_target}` so the reply "
        "lands in that thread. Keep it concise and skip any preamble."
    )


def spawn_title(message: InboundMessage, *, channel_label: str) -> str:
    """A readable session title before auto-title has a chance to run."""
    text = " ".join(message.text.split())
    if text:
        return text[:_MAX_TITLE].rstrip() or channel_label
    return channel_label
