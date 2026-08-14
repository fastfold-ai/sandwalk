from __future__ import annotations

from sandwalk_bench.bixbench import as_is_pack, jsonl_path, load_jsonl, summarize
from sandwalk_bench.pack import expand_matrix, load_pack
from sandwalk_bench.paths import PACKS_DIR
from sandwalk_bench.spawn import (
    bench_kickoff_message,
    build_project_description,
    default_project_name,
    spawn_matrix,
)
from sandwalk_bench.verify import extract_final_answer, grade


def test_sandwalk_pack_loads_and_covers_matrices():
    pack = load_pack(PACKS_DIR / "sandwalk_skills_mcp.yaml")
    assert pack.id == "bio-capybara-full"
    assert len(pack.questions) >= 12
    cells = expand_matrix(pack, "full-coverage")
    assert len(cells) == len(pack.questions)
    assert all(c.title and not c.title.startswith("[bakeoff") for c in cells)


def test_range_and_str_graders():
    g = grade("range_verifier", "(0.07,0.08)", "Answer: 0.075")
    assert g.ok
    g2 = grade("str_verifier", "5:1", "I think the ratio is 5:1")
    assert g2.ok
    assert extract_final_answer("foo\nFINAL_ANSWER: 11\n") == "11"
    assert extract_final_answer("done\nAnswer: 0:0\n") == "0:0"
    assert extract_final_answer("Thus the final answer is 11.") == "11"


def test_spawn_dry_run_includes_project_plan():
    out = spawn_matrix(
        pack_path=PACKS_DIR / "sandwalk_skills_mcp.yaml",
        matrix_name="full-coverage-same-model",
        api_key="",
        dry_run=True,
        project_name="bench · test",
    )
    assert out["project"]["name"] == "bench · test"
    assert "full-coverage-same-model" in out["project"]["description"]
    assert len(out["sessions"]) >= 1
    assert default_project_name("p", "m").startswith("bench · p · m · ")
    pack = load_pack(PACKS_DIR / "sandwalk_skills_mcp.yaml")
    cells = expand_matrix(pack, "full-coverage-same-model")
    desc = build_project_description(
        pack=pack, matrix_name="full-coverage-same-model", cells=cells
    )
    assert "sessions:" in desc
    assert "questions:" in desc
    # Count only — never dump every question id into the project blurb.
    question_line = next(
        line for line in desc.splitlines() if line.startswith("questions:")
    )
    assert "," not in question_line
    assert question_line.split(":", 1)[1].strip().isdigit()


def test_bench_kickoff_message_is_short():
    # Full question text must never be the chat kickoff — only BENCH_PROMPT.md.
    msg = bench_kickoff_message(question_id="mmlu-pro-123")
    assert "mmlu-pro-123" in msg
    assert "BENCH_PROMPT.md" in msg
    assert len(msg) < 200


def test_cached_bixbench_jsonl_schema():
    path = jsonl_path()
    if not path.is_file():
        return  # optional if cache wiped
    rows = load_jsonl()
    assert len(rows) == 50
    info = summarize(rows)
    assert set(info["eval_mode_counts"]) >= {"str_verifier", "range_verifier", "llm_verifier"}
    pack = as_is_pack(rows)
    assert len(pack.questions) == 50
    assert pack.questions[0].source.get("capsule_uuid")
