"""Download missing Bench suite datasets into apps/benchmarking/.cache/."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agent_server.bench_service.bootstrap import bench_root, ensure_sandwalk_bench_importable
from agent_server.models.bench import BenchInstallResponse


class BenchInstallError(RuntimeError):
    """Raised when a suite dataset cannot be installed."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        needs_hf_token: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.needs_hf_token = needs_hf_token


# Public HF JSONL sources (no token). BixBench is gated separately.
_MBPP_URL = (
    "https://huggingface.co/datasets/Muennighoff/mbpp/resolve/main/data/mbpp.jsonl"
)
_LCB_FILES = (
    "test.jsonl",
    "test2.jsonl",
    "test3.jsonl",
    "test4.jsonl",
    "test5.jsonl",
    "test6.jsonl",
)
_LCB_BASE = (
    "https://huggingface.co/datasets/livecodebench/code_generation_lite/resolve/main/"
)

INSTALLABLE_SUITE_IDS = frozenset(
    {"mbpp", "livecodebench", "bixbench-verified-50"}
)


def resolve_hf_token() -> str:
    """Prefer saved Integrations token, then process env."""
    try:
        from agent.config import Config

        config = Config.load()
        stored = str(config.get("mcp.huggingface_api_key") or "").strip()
        if stored:
            return stored
    except Exception:
        pass
    return (
        os.environ.get("HF_TOKEN")
        or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        or ""
    ).strip()


def hf_token_configured() -> bool:
    return bool(resolve_hf_token())


def mcq_cache_dir() -> Path:
    root = bench_root()
    if root is None:
        raise BenchInstallError(
            "Benchmarking package root not found "
            "(expected apps/benchmarking next to the sandwalk checkout).",
            status_code=500,
        )
    path = root / ".cache" / "mcq"
    path.mkdir(parents=True, exist_ok=True)
    return path


def install_suite(suite_id: str, *, force: bool = False) -> BenchInstallResponse:
    """Download a suite dataset into the local bench cache."""
    key = (suite_id or "").strip()
    if key not in INSTALLABLE_SUITE_IDS:
        raise BenchInstallError(
            f"Suite '{key}' is not installable from the dashboard.",
            status_code=404,
        )
    if key == "mbpp":
        path = _install_mbpp(force=force)
        return BenchInstallResponse(
            ok=True,
            suite_id=key,
            path=str(path),
            summary=f"Installed MBPP ({_count_lines(path)} problems).",
        )
    if key == "livecodebench":
        path = _install_livecodebench(force=force)
        return BenchInstallResponse(
            ok=True,
            suite_id=key,
            path=str(path),
            summary=f"Installed LiveCodeBench ({_count_lines(path)} problems).",
        )
    path = _install_bixbench(force=force)
    return BenchInstallResponse(
        ok=True,
        suite_id=key,
        path=str(path),
        summary=f"Installed BixBench-Verified-50 ({_count_lines(path)} tasks).",
    )


def _install_mbpp(*, force: bool) -> Path:
    out = mcq_cache_dir() / "mbpp.jsonl"
    if out.is_file() and out.stat().st_size > 0 and not force:
        return out
    raw = _download_bytes(_MBPP_URL)
    rows: list[dict[str, Any]] = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        task_id = int(item.get("task_id") or 0)
        # Sanitized MBPP test split used by the suite (500 problems).
        if task_id < 11 or task_id > 510:
            continue
        prompt = str(item.get("prompt") or item.get("text") or "").strip()
        tests = list(item.get("test_list") or [])
        if not prompt or not tests:
            continue
        rows.append(
            {
                "task_id": task_id,
                "prompt": prompt,
                "test_list": tests,
                "test_setup_code": str(item.get("test_setup_code") or ""),
            }
        )
    if len(rows) < 100:
        raise BenchInstallError(
            f"MBPP download looked incomplete ({len(rows)} problems).",
            status_code=502,
        )
    rows.sort(key=lambda row: int(row["task_id"]))
    _write_jsonl(out, rows)
    return out


def _install_livecodebench(*, force: bool) -> Path:
    out = mcq_cache_dir() / "livecodebench.jsonl"
    if out.is_file() and out.stat().st_size > 0 and not force:
        return out
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in _LCB_FILES:
        raw = _download_bytes(_LCB_BASE + name)
        for line in raw.decode("utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            qid = str(item.get("question_id") or "").strip()
            if not qid or qid in seen:
                continue
            content = str(item.get("question_content") or "").strip()
            public = item.get("public_test_cases")
            if not content or public in (None, "", []):
                continue
            seen.add(qid)
            rows.append(
                {
                    "question_id": qid,
                    "question_title": str(item.get("question_title") or ""),
                    "question_content": content,
                    "public_test_cases": public
                    if isinstance(public, str)
                    else json.dumps(public),
                    "starter_code": str(item.get("starter_code") or ""),
                    "difficulty": str(item.get("difficulty") or ""),
                }
            )
    if len(rows) < 400:
        raise BenchInstallError(
            f"LiveCodeBench download looked incomplete ({len(rows)} problems).",
            status_code=502,
        )
    _write_jsonl(out, rows)
    return out


def _install_bixbench(*, force: bool) -> Path:
    token = resolve_hf_token()
    if not token:
        raise BenchInstallError(
            "Hugging Face token required. Save it under Integrations → Hugging Face "
            "(or set HF_TOKEN), accept the dataset terms, then Install again.",
            status_code=400,
            needs_hf_token=True,
        )
    if not ensure_sandwalk_bench_importable():
        raise BenchInstallError(
            "sandwalk-bench package is not importable.",
            status_code=500,
        )
    from sandwalk_bench.bixbench import download_jsonl, jsonl_path

    try:
        path = download_jsonl(token=token, force=force)
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise BenchInstallError(
                "Hugging Face rejected the token or dataset terms are not accepted. "
                "Update Integrations → Hugging Face and accept "
                "phylobio/BixBench-Verified-50 on Hugging Face.",
                status_code=401,
                needs_hf_token=True,
            ) from exc
        raise BenchInstallError(
            f"BixBench download failed (HTTP {exc.code}).",
            status_code=502,
        ) from exc
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "HF token" in msg or "HF_TOKEN" in msg:
            raise BenchInstallError(
                msg,
                status_code=400,
                needs_hf_token=True,
            ) from exc
        raise BenchInstallError(msg, status_code=502) from exc
    if not path.is_file():
        path = jsonl_path()
    return path


def _download_bytes(url: str, *, token: str | None = None) -> bytes:
    headers = {"User-Agent": "sandwalk-bench"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=300) as resp:  # noqa: S310 — fixed HF URLs
            return resp.read()
    except HTTPError as exc:
        raise BenchInstallError(
            f"Download failed for {url} (HTTP {exc.code}).",
            status_code=502,
        ) from exc
    except URLError as exc:
        raise BenchInstallError(
            f"Download failed for {url}: {exc.reason}",
            status_code=502,
        ) from exc


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def _count_lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
