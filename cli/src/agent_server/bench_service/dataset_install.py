"""Download missing Bench suite datasets into apps/benchmarking/.cache/."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from agent_server.bench_service.bootstrap import (
    bench_cache_root,
    ensure_sandwalk_bench_importable,
)
from agent_server.models.bench import BenchInstallResponse, BenchUninstallResponse

ProgressCb = Callable[..., None]

logger = logging.getLogger(__name__)


class BenchInstallError(RuntimeError):
    """Raised when a suite dataset cannot be installed."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        needs_hf_token: bool = False,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.needs_hf_token = needs_hf_token
        # Upstream HTTP code when this wraps a download failure (e.g. 429).
        self.http_status = http_status


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
    {
        "mbpp",
        "livecodebench",
        "bixbench-verified-50",
        "mmlu",
        "mmlu-pro",
        "arc-challenge",
    }
)

# MCQ corpora ship only 30-row sample fixtures in git. The full sets come from
# the public HF rows API (no token, 100 rows per page) so this stays dependency
# free — the parquet files would need pyarrow, which is only an optional extra.
_HF_ROWS_URL = "https://datasets-server.huggingface.co/rows"
_HF_ROWS_PAGE = 100
_HF_ROWS_RETRIES = 5
_HF_ROWS_BACKOFF = 2.0
_HF_ROWS_PAGE_PAUSE = 0.15

_MCQ_SOURCES: dict[str, dict[str, str]] = {
    "mmlu": {
        "dataset": "cais/mmlu",
        "config": "all",
        "split": "test",
        "fixture": "mmlu_test.jsonl",
        "title": "MMLU",
        "parquet": (
            "https://huggingface.co/datasets/cais/mmlu/resolve/main/"
            "all/test-00000-of-00001.parquet"
        ),
    },
    "mmlu-pro": {
        "dataset": "TIGER-Lab/MMLU-Pro",
        "config": "default",
        "split": "test",
        "fixture": "mmlu_pro_test.jsonl",
        "title": "MMLU-Pro",
        "parquet": (
            "https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro/resolve/main/"
            "data/test-00000-of-00001.parquet"
        ),
    },
    "arc-challenge": {
        "dataset": "allenai/ai2_arc",
        "config": "ARC-Challenge",
        "split": "test",
        "fixture": "arc_challenge.jsonl",
        "title": "ARC-C",
        "parquet": (
            "https://huggingface.co/datasets/allenai/ai2_arc/resolve/main/"
            "ARC-Challenge/test-00000-of-00001.parquet"
        ),
    },
}

_LETTERS = "ABCDEFGHIJ"

# Cache filenames for the code suites (mirrors CODING_SUITES.full_fixture; kept
# here so uninstall does not import the suite module).
_CODING_FIXTURES = {
    "mbpp": "mbpp.jsonl",
    "livecodebench": "livecodebench.jsonl",
}


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
    path = bench_cache_root() / ".cache" / "mcq"
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
    if key in _MCQ_SOURCES:
        path = _install_mcq(key, force=force, on_progress=on_progress)
        title = _MCQ_SOURCES[key]["title"]
        return BenchInstallResponse(
            ok=True,
            suite_id=key,
            path=str(path),
            summary=f"Installed {title} ({_count_lines(path)} questions).",
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


def _install_mcq(
    suite_id: str,
    *,
    force: bool,
    on_progress: ProgressCb | None = None,
) -> Path:
    """Page the full MCQ corpus out of the HF rows API into the bench cache."""
    src = _MCQ_SOURCES[suite_id]
    out = mcq_cache_dir() / src["fixture"]
    if out.is_file() and out.stat().st_size > 0 and not force:
        return out

    title = src["title"]
    _emit(
        on_progress,
        label=src["fixture"],
        files_done=0,
        files_total=1,
        bytes_done=0,
        bytes_total=None,
        summary=f"Downloading {title}…",
    )

    rows = _mcq_rows_from_parquet(suite_id, src, on_progress=on_progress)
    if rows is None:
        rows = _mcq_rows_from_api(suite_id, src, on_progress=on_progress)

    if not rows:
        raise BenchInstallError(
            f"{title} download returned no usable questions.",
            status_code=502,
        )

    _write_jsonl(out, rows)
    _emit(
        on_progress,
        label="Done",
        files_done=1,
        files_total=1,
        bytes_done=len(rows),
        bytes_total=len(rows),
        summary=f"Installed {title} ({len(rows)} questions).",
    )
    return out


def _mcq_rows_from_parquet(
    suite_id: str,
    src: dict[str, str],
    *,
    on_progress: ProgressCb | None = None,
) -> list[dict[str, Any]] | None:
    """Preferred path: one request for the whole corpus.

    Returns None when no parquet reader is installed, so the caller can fall back
    to the paged rows API. Parquet keeps this to a single request — the rows API
    needs ~141 pages for MMLU and gets rate-limited partway through.
    """
    url = src.get("parquet")
    if not url:
        return None
    read = _parquet_reader()
    if read is None:
        return None

    def on_chunk(done: int, total: int | None) -> None:
        _emit(
            on_progress,
            label=src["fixture"],
            files_done=0,
            files_total=1,
            bytes_done=done,
            bytes_total=total,
            summary=f"Downloading {src['title']}…",
        )

    raw = _download_bytes(url, token=resolve_hf_token() or None, on_chunk=on_chunk)
    try:
        records = read(raw)
    except Exception as exc:  # noqa: BLE001 — fall back to the rows API
        logger.warning(
            "Parquet parse failed for %s (%s); using the rows API", suite_id, exc
        )
        return None
    rows: list[dict[str, Any]] = []
    for record in records:
        normalized = _normalize_mcq_row(suite_id, record)
        if normalized is not None:
            rows.append(normalized)
    return rows or None


def parquet_reader_available() -> bool:
    """True when a parquet reader is importable (fast single-request install)."""
    return _parquet_reader() is not None


def missing_parquet_dependency() -> str | None:
    """Hint for the UI when the fast install path is unavailable.

    Without pyarrow/duckdb, installs fall back to the paged rows API, which
    Hugging Face rate-limits on the larger corpora (MMLU needs ~141 pages).
    """
    if parquet_reader_available():
        return None
    return (
        "Install the 'bench' extra for fast dataset downloads: "
        "uv sync --extra bench (or: pip install -e '.[bench]') in cli/. "
        "Without it, downloads use a paged API that Hugging Face may rate-limit."
    )


def _parquet_reader() -> Callable[[bytes], list[dict[str, Any]]] | None:
    """Return a bytes -> list[dict] parquet reader, or None when unavailable.

    pyarrow and duckdb both ship in the ``api`` / ``all`` extras; neither is a
    core dependency, so this stays optional.
    """
    try:
        import pyarrow.parquet as pq  # noqa: PLC0415

        def _read_pyarrow(raw: bytes) -> list[dict[str, Any]]:
            import io

            return pq.read_table(io.BytesIO(raw)).to_pylist()

        return _read_pyarrow
    except ImportError:
        pass

    try:
        import duckdb  # noqa: PLC0415

        def _read_duckdb(raw: bytes) -> list[dict[str, Any]]:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".parquet") as fh:
                fh.write(raw)
                fh.flush()
                rel = duckdb.sql(f"SELECT * FROM read_parquet('{fh.name}')")
                columns = [str(c) for c in rel.columns]
                return [dict(zip(columns, row, strict=False)) for row in rel.fetchall()]

        return _read_duckdb
    except ImportError:
        return None


def _mcq_rows_from_api(
    suite_id: str,
    src: dict[str, str],
    *,
    on_progress: ProgressCb | None = None,
) -> list[dict[str, Any]]:
    """Fallback: page the HF rows API (100 rows per request)."""
    title = src["title"]
    rows: list[dict[str, Any]] = []
    total: int | None = None
    offset = 0
    while True:
        payload = _fetch_hf_rows(src, offset=offset, length=_HF_ROWS_PAGE)
        if total is None:
            raw_total = payload.get("num_rows_total")
            total = int(raw_total) if isinstance(raw_total, int) else None
        page = payload.get("rows") or []
        if not page:
            break
        for entry in page:
            row = entry.get("row") if isinstance(entry, dict) else None
            if not isinstance(row, dict):
                continue
            normalized = _normalize_mcq_row(suite_id, row)
            if normalized is not None:
                rows.append(normalized)
        offset += len(page)
        _emit(
            on_progress,
            label=src["fixture"],
            files_done=0,
            files_total=1,
            bytes_done=len(rows),
            bytes_total=total,
            summary=f"Downloading {title} ({len(rows)}/{total or '?'} questions)…",
        )
        if total is not None and offset >= total:
            break
        if len(page) < _HF_ROWS_PAGE:
            break
        # Gentle pacing: the public rows API 429s on sustained paging.
        time.sleep(_HF_ROWS_PAGE_PAUSE)
    return rows


def _fetch_hf_rows(
    src: dict[str, str], *, offset: int, length: int
) -> dict[str, Any]:
    query = urlencode(
        {
            "dataset": src["dataset"],
            "config": src["config"],
            "split": src["split"],
            "offset": offset,
            "length": length,
        }
    )
    url = f"{_HF_ROWS_URL}?{query}"
    # Full MMLU is ~141 pages and the public rows API throttles sustained
    # paging, so retry 429/5xx with backoff instead of failing the install.
    # An HF token (Integrations → Hugging Face) raises the limit when present.
    token = resolve_hf_token() or None
    for attempt in range(_HF_ROWS_RETRIES):
        try:
            raw = _download_bytes(url, token=token)
            break
        except BenchInstallError as exc:
            retryable = exc.http_status in {429, 500, 502, 503, 504}
            if not retryable or attempt == _HF_ROWS_RETRIES - 1:
                if exc.http_status == 429:
                    raise BenchInstallError(
                        f"Hugging Face rate-limited the {src['title']} download. "
                        "Wait a minute and click Install again"
                        + (
                            "."
                            if token
                            else ", or add a Hugging Face token under "
                            "Integrations for higher limits."
                        ),
                        status_code=429,
                        http_status=429,
                    ) from exc
                raise
            time.sleep(_HF_ROWS_BACKOFF * (2**attempt))

    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise BenchInstallError(
            f"Unexpected response from Hugging Face for {src['dataset']}.",
            status_code=502,
        ) from exc
    if not isinstance(payload, dict):
        raise BenchInstallError(
            f"Unexpected response from Hugging Face for {src['dataset']}.",
            status_code=502,
        )
    return payload


def _as_list(value: Any) -> list[Any]:
    """Coerce parquet/JSON sequence values (list, tuple, numpy array) to a list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            result = tolist()
        except Exception:  # noqa: BLE001
            return []
        return list(result) if isinstance(result, (list, tuple)) else []
    return []


def _normalize_mcq_row(suite_id: str, row: dict[str, Any]) -> dict[str, Any] | None:
    """Map upstream schemas onto the loader's question/choices/answer shape.

    Handles both the rows-API JSON and parquet reads, where sequence columns can
    arrive as numpy arrays and integer answers as numpy scalars.
    """
    if suite_id == "mmlu":
        choices = [str(c) for c in _as_list(row.get("choices"))]
        raw_answer = row.get("answer")
        try:
            answer = int(raw_answer)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        if not choices or not 0 <= answer < len(choices):
            return None
        return {
            "question": str(row.get("question") or ""),
            "choices": choices,
            "answer": _LETTERS[answer],
            "subject": str(row.get("subject") or "unknown"),
        }

    if suite_id == "mmlu-pro":
        choices = [str(c) for c in _as_list(row.get("options"))]
        letter = str(row.get("answer") or "").strip().upper()[:1]
        if not choices or letter not in _LETTERS[: len(choices)]:
            return None
        return {
            "id": str(row.get("question_id") or ""),
            "question": str(row.get("question") or ""),
            "choices": choices,
            "answer": letter,
            "subject": str(row.get("category") or "unknown"),
        }

    # ARC-Challenge: choices arrive as {"text": [...], "label": [...]}.
    raw_choices = row.get("choices")
    if not isinstance(raw_choices, dict):
        return None
    texts = [str(t) for t in _as_list(raw_choices.get("text"))]
    labels = [str(x).strip().upper() for x in _as_list(raw_choices.get("label"))]
    key = str(row.get("answerKey") or "").strip().upper()
    if not texts or not labels or key not in labels:
        return None
    return {
        "id": str(row.get("id") or ""),
        "question": str(row.get("question") or ""),
        "choices": texts,
        "labels": labels,
        "answer": key,
        "subject": "science",
    }


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
            http_status=exc.code,
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
    """Count JSONL records the way the loaders read them (newline-delimited).

    ``str.splitlines`` also breaks on U+0085 / U+2028 / U+2029, which appear
    inside a couple of MMLU questions — that over-counted the install summary.
    """
    with path.open(encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def suite_cache_paths(suite_id: str) -> list[Path]:
    """Local cache files/dirs a suite owns (may be absent)."""
    key = (suite_id or "").strip()
    root = bench_cache_root()
    if key in _MCQ_SOURCES:
        return [root / ".cache" / "mcq" / _MCQ_SOURCES[key]["fixture"]]
    if key in _CODING_FIXTURES:
        return [root / ".cache" / "mcq" / _CODING_FIXTURES[key]]
    if key == "bixbench-verified-50":
        # Includes downloaded capsule data, which dwarfs the JSONL.
        return [root / ".cache" / "bixbench-verified-50"]
    return []


def _path_size(path: Path) -> int:
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    if path.is_dir():
        total = 0
        for child in path.rglob("*"):
            if child.is_file():
                try:
                    total += child.stat().st_size
                except OSError:
                    continue
        return total
    return 0


def suite_installed_bytes(suite_id: str) -> int:
    """Disk usage for a suite's cached dataset (0 when nothing is cached)."""
    return sum(_path_size(path) for path in suite_cache_paths(suite_id))


def suite_installed_count(suite_id: str) -> int | None:
    """Cached question count for JSONL suites, else None."""
    for path in suite_cache_paths(suite_id):
        if path.is_file():
            try:
                return _count_lines(path)
            except OSError:
                return None
    return None


def cache_root() -> Path | None:
    return bench_cache_root() / ".cache"


def total_cache_bytes() -> int:
    """Disk usage for the whole bench cache."""
    root = cache_root()
    return 0 if root is None else _path_size(root)


def uninstall_suite(suite_id: str) -> BenchUninstallResponse:
    """Delete a suite's cached dataset to reclaim disk space."""
    # Imported lazily: install_jobs imports this module, so a top-level import
    # would be circular.
    from agent_server.bench_service.install_jobs import (
        clear_install_job,
        is_installing,
    )

    key = (suite_id or "").strip()
    if key not in INSTALLABLE_SUITE_IDS:
        raise BenchInstallError(
            f"Suite '{key}' has no removable dataset.",
            status_code=404,
        )
    if is_installing(key):
        raise BenchInstallError(
            "That dataset is still downloading. Wait for it to finish, then remove it.",
            status_code=409,
        )

    freed = 0
    removed: list[str] = []
    for path in suite_cache_paths(key):
        size = _path_size(path)
        if size == 0 and not path.exists():
            continue
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as exc:
            raise BenchInstallError(
                f"Could not remove {path.name}: {exc}",
                status_code=500,
            ) from exc
        freed += size
        removed.append(path.name)

    clear_install_job(key)
    if not removed:
        return BenchUninstallResponse(
            ok=True,
            suite_id=key,
            summary="Nothing cached for this suite.",
            freed_bytes=0,
        )
    return BenchUninstallResponse(
        ok=True,
        suite_id=key,
        summary=f"Removed {', '.join(removed)} ({_human_bytes(freed)} freed).",
        freed_bytes=freed,
        removed=removed,
    )


def _human_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"
