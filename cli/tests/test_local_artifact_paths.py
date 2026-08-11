"""Tests for deterministic local artifact path extraction / answer append."""

from __future__ import annotations

from agent.local_artifact_paths import (
    append_downloaded_artifacts_block,
    collect_paths_from_tool_calls,
    extract_local_artifact_paths,
)
from agent.mcp_server.formatting import _format_tool_result


def test_extract_from_collect_artifacts_json():
    stdout = """{
  "job_id": "13b7286e-6927-42cc-bb25-94a9864ce67d",
  "local_paths": [
    "/Users/me/.sandwalk/workspaces/x/artifacts/fold/13b7286e-6927-42cc-bb25-94a9864ce67d/output_13b7286e-6927-42cc-bb25-94a9864ce67d_model_0.cif"
  ],
  "downloads": {
    "downloaded": [
      {
        "label": "Primary CIF",
        "url": "https://artifacts.fastfold.ai/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb/cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc/output.cif",
        "path": "/Users/me/.sandwalk/workspaces/x/artifacts/fold/13b7286e-6927-42cc-bb25-94a9864ce67d/output_13b7286e-6927-42cc-bb25-94a9864ce67d_model_0.cif"
      }
    ]
  },
  "artifacts": []
}"""
    paths = extract_local_artifact_paths(stdout)
    assert any(p.endswith("_model_0.cif") for p in paths)
    assert all("..." not in p for p in paths)


def test_extract_downloaded_local_paths_block():
    text = """DOWNLOADED_LOCAL_PATHS:
/Users/me/a.cif
/Users/me/b.svg
- SAFE Primary CIF: https://example.com/x
"""
    assert extract_local_artifact_paths(text) == [
        "/Users/me/a.cif",
        "/Users/me/b.svg",
    ]


def test_format_tool_result_keeps_local_paths_before_long_stdout():
    long_urls = "https://artifacts.fastfold.ai/" + ("a" * 2000)
    result = {
        "summary": "Command succeeded (exit 0). Local files:\n/Users/me/out.cif",
        "local_paths": ["/Users/me/out.cif", "/Users/me/plot.svg"],
        "stdout": long_urls,
        "exit_code": 0,
    }
    text = _format_tool_result(result)
    assert "/Users/me/out.cif" in text
    assert "/Users/me/plot.svg" in text
    # local_paths block must appear before the truncated stdout tail marker.
    assert text.index("local_paths:") < text.index("stdout:")


def test_append_block_only_adds_missing_paths():
    summary = "Fold done. See /Users/me/out.cif"
    out = append_downloaded_artifacts_block(
        summary,
        ["/Users/me/out.cif", "/Users/me/plot.svg"],
    )
    assert "Downloaded artifacts:" in out
    assert "/Users/me/plot.svg" in out
    # Already-cited path should not be duplicated in the block.
    assert out.count("/Users/me/out.cif") == 1


def test_collect_from_tool_calls_result_text():
    tool_calls = [
        {
            "name": "shell.run",
            "result_text": (
                "local_paths:\n"
                "/Users/me/.sandwalk/workspaces/x/artifacts/fold/j/output_j_model_0.cif\n"
                "stdout: {...}"
            ),
        }
    ]
    paths = collect_paths_from_tool_calls(tool_calls)
    assert paths == [
        "/Users/me/.sandwalk/workspaces/x/artifacts/fold/j/output_j_model_0.cif"
    ]
