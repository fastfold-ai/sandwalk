"""Common question schema (BixBench-aligned + sandwalk extensions)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EvalMode = Literal[
    "str_verifier",
    "range_verifier",
    "llm_verifier",
    "mcq",
    "checklist",
    "code_exec",
]


@dataclass
class Question:
    """Normalized benchmark question.

    Core fields mirror [phylobio/BixBench-Verified-50](https://huggingface.co/datasets/phylobio/BixBench-Verified-50):
    ``question_id`` / ``question`` / ``ideal`` / ``eval_mode`` / capsule metadata.

    Sandwalk extensions: ``skills``, ``mcps``, ``prompt`` (agent-facing), ``inputs``.
    """

    id: str
    question: str
    ideal: str | None = None
    eval_mode: EvalMode | str = "checklist"
    title: str = ""
    focus: str = ""
    skills: list[str] = field(default_factory=list)
    mcps: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    distractors: list[str] = field(default_factory=list)
    prompt: str = ""
    fixture_dir: str | None = None
    default_model: str | None = None
    source: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def agent_prompt(self) -> str:
        return self.prompt or self.question


@dataclass
class Pack:
    """A loadable YAML (or future HF) question pack."""

    id: str
    version: str
    description: str = ""
    questions: list[Question] = field(default_factory=list)
    models: dict[str, str] = field(default_factory=dict)
    matrices: dict[str, Any] = field(default_factory=dict)
    title_template: str = "{title} · {model_short}"
    prompt_prefix: str = ""
    prompt_suffix_template: str = ""
    inputs_dir: str | None = None
    path: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, question_id: str) -> Question:
        for q in self.questions:
            if q.id == question_id:
                return q
        raise KeyError(question_id)


@dataclass
class MatrixCell:
    question_id: str
    model_key: str
    model_id: str
    provider: str = "openrouter"
    title: str = ""
    prompt: str = ""
    question: Question | None = None
