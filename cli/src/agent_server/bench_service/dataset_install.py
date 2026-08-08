"""Download missing Bench suite datasets into apps/benchmarking/.cache/."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agent_server.bench_service.bootstrap import bench_root, ensure_sandwalk_bench_importable
from agent_server.models.bench import BenchInstallResponse

ProgressCb = Callable[..., None]


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


def install_suite(
    suite_id: str,
    *,
    force: bool = False,
    on_progress: ProgressCb | None = None,
) -> BenchInstallResponse:
    """Download a suite dataset into the local bench cache."""
    key = (suite_id or "").strip()
    if key not in INSTALLABLE_SUITE_IDS:
        raise BenchInstallError(
            f"Suite '{key}' is not installable from the dashboard.",
            status_code=404,
        )
    if key == "mbpp":
        path = _install_mbpp(force=force, on_progress=on_progress)
        return BenchInstallResponse(
            ok=True,
            suite_id=key,
            path=str(path),
            summary=f"Installed MBPP ({_count_lines(path)} problems).",
        )
    if key == "livecodebench":
        path = _install_livecodebench(force=force, on_progress=on_progress)
        return BenchInstallResponse(
            ok=True,
            suite_id=key,
            path=str(path),
            summary=f"Installed LiveCodeBench ({_count_lines(path)} problems).",
        )
    path = _install_bixbench(force=force, on_progress=on_progress)
    return BenchInstallResponse(
        ok=True,
        suite_id=key,
        path=str(path),
        summary=f"Installed BixBench-Verified-50 ({_count_lines(path)} tasks).",
    )


def _emit(on_progress: ProgressCb | None, **kwargs: Any) -> None:
    if on_progress is None:
        return
    on_progress(**kwargs)


def _install_mbpp(*, force: bool, on_progress: ProgressCb | None = None) -> Path:
    out = mcq_cache_dir() / "mbpp.jsonl"
    if out.is_file() and out.stat().st_size > 0 and not force:
        return out
    _emit(
        on_progress,
        label="mbpp.jsonl",
        files_done=0,
        files_total=1,
        bytes_done=0,
        bytes_total=None,
        summary="Downloading MBPP…",
    )
    raw = _download_bytes(
        _MBPP_URL,
        on_chunk=lambda done, total: _emit(
            on_progress,
            label="mbpp.jsonl",
            files_done=0,
            files_total=1,
            bytes_done=done,
            bytes_total=total,
        ),
    )
    _emit(
        on_progress,
        label="Parsing MBPP…",
        files_done=0,
        files_total=1,
        bytes_done=len(raw),
        bytes_total=len(raw),
    )
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
    _emit(
        on_progress,
        label="Done",
        files_done=1,
        files_total=1,
        bytes_done=len(raw),
        bytes_total=len(raw),
    )
    return out


def _install_livecodebench(
    *, force: bool, on_progress: ProgressCb | None = None
) -> Path:
    out = mcq_cache_dir() / "livecodebench.jsonl"
    if out.is_file() and out.stat().st_size > 0 and not force:
        return out
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    files_total = len(_LCB_FILES)
    bytes_before = 0
    for index, name in enumerate(_LCB_FILES):
        _emit(
            on_progress,
            label=name,
            files_done=index,
            files_total=files_total,
            bytes_done=bytes_before,
            bytes_total=None,
            summary=f"Downloading {name}…",
        )

        def _chunk(
            done: int,
            total: int | None,
            *,
            base: int = bytes_before,
            file_index: int = index,
            file_name: str = name,
        ) -> None:
            # Prefer aggregate known total when Content-Length is present.
            file_total = total if total and total > 0 else None
            _emit(
                on_progress,
                label=file_name,
                files_done=file_index,
                files_total=files_total,
                bytes_done=base + done,
                bytes_total=(base + file_total) if file_total else None,
            )

        raw = _download_bytes(_LCB_BASE + name, on_chunk=_chunk)
        bytes_before += len(raw)
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
        _emit(
            on_progress,
            label=name,
            files_done=index + 1,
            files_total=files_total,
            bytes_done=bytes_before,
            bytes_total=bytes_before,
        )
    if len(rows) < 400:
        raise BenchInstallError(
            f"LiveCodeBench download looked incomplete ({len(rows)} problems).",
            status_code=502,
        )
    _emit(
        on_progress,
        label="Writing livecodebench.jsonl…",
        files_done=files_total,
        files_total=files_total,
        bytes_done=bytes_before,
        bytes_total=bytes_before,
    )
    _write_jsonl(out, rows)
    return out


def _install_bixbench(
    *, force: bool, on_progress: ProgressCb | None = None
) -> Path:
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

    _emit(
        on_progress,
        label="BixBench-Verified-50",
        files_done=0,
        files_total=1,
        summary="Downloading BixBench-Verified-50 from Hugging Face…",
    )
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
    size = path.stat().st_size if path.is_file() else 0
    _emit(
        on_progress,
        label="Done",
        files_done=1,
        files_total=1,
        bytes_done=size,
        bytes_total=size or None,
    )
    return path


def _download_bytes(
    url: str,
    *,
    token: str | None = None,
    on_chunk: Callable[[int, int | None], None] | None = None,
) -> bytes:
    headers = {"User-Agent": "sandwalk-bench"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=300) as resp:  # noqa: S310 — fixed HF URLs
            raw_len = resp.headers.get("Content-Length")
            total = int(raw_len) if raw_len and str(raw_len).isdigit() else None
            chunks: list[bytes] = []
            done = 0
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
                done += len(chunk)
                if on_chunk is not None:
                    on_chunk(done, total)
            return b"".join(chunks)
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
