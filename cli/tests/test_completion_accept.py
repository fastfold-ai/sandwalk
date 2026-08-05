"""Enter accepts @ file chips without submitting."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from ui.terminal.completion_accept import accept_file_completion, accept_slash_completion


class _Buf:
    def __init__(self, text: str = "", completions=None, current=None):
        self.text = text
        self.complete_state = SimpleNamespace(
            completions=completions or [],
            complete_index=0 if current is not None else None,
            current_completion=current,
        )
        self.applied = None
        self.cancelled = False
        self.inserted = []

    @property
    def document(self):
        return SimpleNamespace(text_before_cursor=self.text, text_after_cursor="")

    def go_to_completion(self, idx: int):
        self.complete_state.complete_index = idx
        self.complete_state.current_completion = self.complete_state.completions[idx]

    def apply_completion(self, completion):
        self.applied = completion
        self.text = getattr(completion, "text", "") or ""

    def insert_text(self, text: str):
        self.inserted.append(text)
        self.text += text

    def cancel_completion(self):
        self.cancelled = True
        self.complete_state = None


def test_accept_file_completion_inserts_chip_without_submit():
    chip = SimpleNamespace(text="@[notes.md]")
    buf = _Buf(text="@note", completions=[chip], current=None)
    assert accept_file_completion(buf) is True
    assert buf.applied is chip
    assert buf.text.endswith(" ")
    assert buf.cancelled is True


def test_accept_file_completion_ignores_tool_completions():
    tool = SimpleNamespace(text="#target.coessentiality")
    buf = _Buf(text="#targ", completions=[tool], current=tool)
    assert accept_file_completion(buf) is False
    assert buf.applied is None


def test_accept_slash_completion_applies():
    help_c = SimpleNamespace(text="/help")
    buf = _Buf(text="/he", completions=[help_c], current=None)
    assert accept_slash_completion(buf) is True
    assert buf.applied is help_c


def test_accept_slash_completion_after_preceding_text():
    help_c = SimpleNamespace(text="/help")
    buf = _Buf(text="hi /he", completions=[help_c], current=help_c)
    assert accept_slash_completion(buf) is True
    assert buf.applied is help_c
