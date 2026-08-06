"""Unit tests for unsupported multimodal content stripping."""

from __future__ import annotations

import base64
from pathlib import Path

from langchain_core.messages import HumanMessage, ToolMessage

from agent.deepagents_runtime.modality_sanitize import (
    detect_block_modality,
    sanitize_content_blocks,
    sanitize_messages,
    unsupported_modalities,
)


def test_detect_lc_image_and_openai_image_url():
    assert detect_block_modality(
        {"type": "image", "base64": "abcd", "mime_type": "image/png"}
    ) == "image"
    assert detect_block_modality(
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,abcd"},
        }
    ) == "image"
    assert detect_block_modality({"type": "text", "text": "hi"}) is None


def test_deepseek_marks_image_unsupported():
    kinds = unsupported_modalities("deepseek", "deepseek-v4-flash")
    assert "image" in kinds


def test_sanitize_replaces_image_and_saves(tmp_path: Path):
    png = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode("ascii")
    content = [
        {"type": "text", "text": "viewport ok"},
        {"type": "image", "base64": png, "mime_type": "image/png"},
    ]
    new_content, changed = sanitize_content_blocks(
        content,
        unsupported=frozenset({"image"}),
        save_dir=tmp_path / "tool-images",
    )
    assert changed
    assert new_content[0]["text"] == "viewport ok"
    assert new_content[1]["type"] == "text"
    assert "cannot accept image input" in new_content[1]["text"]
    assert "Saved to" in new_content[1]["text"]
    saved = list((tmp_path / "tool-images").glob("image-*.png"))
    assert len(saved) == 1
    assert saved[0].read_bytes().startswith(b"\x89PNG")


def test_sanitize_messages_tool_and_human():
    png = base64.b64encode(b"img").decode("ascii")
    messages = [
        HumanMessage(
            content=[
                {"type": "text", "text": "look"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{png}"},
                },
            ]
        ),
        ToolMessage(
            content=[
                {"type": "image", "base64": png, "mime_type": "image/png"},
            ],
            tool_call_id="c1",
        ),
    ]
    out, changed = sanitize_messages(
        messages, unsupported=frozenset({"image"}), save_dir=None
    )
    assert changed
    assert all(
        isinstance(block, dict) and block.get("type") == "text"
        for msg in out
        for block in msg.content
        if isinstance(msg.content, list)
    )
    assert "cannot accept image" in out[1].content[0]["text"]


def test_sanitize_noop_when_supported():
    content = [
        {"type": "image", "base64": "abcd", "mime_type": "image/png"},
    ]
    new_content, changed = sanitize_content_blocks(
        content, unsupported=frozenset(), save_dir=None
    )
    assert not changed
    assert new_content is content
