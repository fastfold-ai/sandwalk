"""Load YAML question packs into the common schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from sandwalk_bench.paths import PACKS_DIR
from sandwalk_bench.schema import MatrixCell, Pack, Question


def list_packs() -> list[Path]:
    return sorted(PACKS_DIR.glob("*.yaml")) + sorted(PACKS_DIR.glob("*.yml"))


def load_pack(path: str | Path) -> Pack:
    p = Path(path)
    if not p.is_file():
        alt = PACKS_DIR / p.name
        if alt.is_file():
            p = alt
        else:
            raise FileNotFoundError(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    questions = [_question(item) for item in raw.get("questions") or []]
    return Pack(
        id=str(raw.get("pack") or p.stem),
        version=str(raw.get("version") or "0"),
        description=str(raw.get("description") or ""),
        questions=questions,
        models=dict(raw.get("models") or {}),
        matrices=dict(raw.get("matrices") or {}),
        title_template=str(raw.get("title_template") or "{title} · {model_short}"),
        prompt_prefix=str(raw.get("prompt_prefix") or ""),
        prompt_suffix_template=str(raw.get("prompt_suffix_template") or ""),
        inputs_dir=raw.get("inputs_dir"),
        path=str(p),
        raw=raw,
    )


def _question(item: dict[str, Any]) -> Question:
    qid = str(item.get("id") or item.get("question_id") or "")
    upstream = str(item.get("upstream_question") or item.get("question") or "")
    prompt = str(item.get("prompt") or upstream)
    return Question(
        id=qid,
        question=upstream or prompt,
        ideal=None if item.get("ideal") is None else str(item.get("ideal")),
        eval_mode=str(item.get("eval_mode") or "checklist"),
        title=str(item.get("title") or qid),
        focus=str(item.get("focus") or ""),
        skills=list(item.get("skills") or []),
        mcps=list(item.get("mcps") or []),
        inputs=list(item.get("inputs") or []),
        distractors=list(item.get("distractors") or []),
        prompt=prompt,
        fixture_dir=item.get("fixture_dir"),
        default_model=item.get("default_model"),
        source=dict(item.get("source") or {}),
        metadata={
            k: v
            for k, v in item.items()
            if k
            not in {
                "id",
                "question_id",
                "question",
                "upstream_question",
                "ideal",
                "eval_mode",
                "title",
                "focus",
                "skills",
                "mcps",
                "inputs",
                "distractors",
                "prompt",
                "fixture_dir",
                "default_model",
                "source",
            }
        },
    )


def expand_matrix(pack: Pack, matrix_name: str) -> list[MatrixCell]:
    matrix = pack.matrices.get(matrix_name)
    if not matrix:
        raise KeyError(f"matrix {matrix_name!r} not in pack {pack.id}")
    provider = str(matrix.get("provider") or "openrouter")
    mode = str(matrix.get("mode") or "pairs")
    cells: list[MatrixCell] = []

    if mode == "pairs":
        for pair in matrix.get("pairs") or []:
            qid = str(pair["question"])
            mkey = str(pair["model"])
            cells.append(_cell(pack, qid, mkey, provider))
        return cells

    if mode == "product":
        qids = [str(x) for x in matrix.get("questions") or []]
        mkeys = [str(x) for x in matrix.get("models") or []]
        for qid in qids:
            for mkey in mkeys:
                cells.append(_cell(pack, qid, mkey, provider))
        return cells

    raise ValueError(f"unsupported matrix mode: {mode}")


def _cell(pack: Pack, qid: str, mkey: str, provider: str) -> MatrixCell:
    q = pack.get(qid)
    mid = pack.models.get(mkey, mkey)
    model_short = mid.split("/")[-1]
    title = pack.title_template.format(
        title=q.title or q.id,
        model_short=model_short,
        model=mid,
        id=q.id,
    )
    suffix = pack.prompt_suffix_template.format(model=mid, model_short=model_short)
    prompt = f"{pack.prompt_prefix}{q.agent_prompt}{suffix}"
    return MatrixCell(
        question_id=qid,
        model_key=mkey,
        model_id=mid,
        provider=provider,
        title=title,
        prompt=prompt,
        question=q,
    )


def render_agent_prompt(pack: Pack, question: Question, model_id: str) -> str:
    model_short = model_id.split("/")[-1]
    suffix = pack.prompt_suffix_template.format(model=model_id, model_short=model_short)
    return f"{pack.prompt_prefix}{question.agent_prompt}{suffix}"
