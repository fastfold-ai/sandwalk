"""Bridge to the external Llama macOS app (https://github.com/ggml-org/Llama-macOS).

Sandwalk does not embed the menu-bar app. It installs the ``llama`` CLI from
https://llama.app/install.sh, runs ``llama serve`` on port 9931, and uses
``llama download`` for catalog models.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from collections import deque
from pathlib import Path
from typing import Any

import httpx

LLAMA_BASE_URL = "http://127.0.0.1:9931/v1"
_SERVE_PORT = 9931
_MODELS_URL = f"{LLAMA_BASE_URL}/models"
_CATALOG_URL = "https://llama.app/v1/catalog.json"
_INSTALL_URL = "https://llama.app/install.sh"

_lock = threading.Lock()
_state: dict[str, str] = {"phase": "idle", "detail": ""}
_debug: dict[str, Any] = {}
_serve_log: deque[str] = deque(maxlen=80)
_serve_command: list[str] = []
# model id -> "loading" or the last load error
_load_jobs: dict[str, str] = {}


def _app_paths() -> list[Path]:
    home = Path.home()
    return [
        Path("/Applications/Llama.app"),
        home / "Applications" / "Llama.app",
    ]


def app_installed() -> bool:
    return any(path.exists() for path in _app_paths())


def _models_payload() -> list[dict[str, Any]] | None:
    try:
        response = httpx.get(_MODELS_URL, timeout=1.5)
    except httpx.HTTPError:
        return None
    if response.status_code >= 400:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _arg(args: list[Any], flag: str) -> str | None:
    try:
        index = args.index(flag)
    except ValueError:
        return None
    if index + 1 >= len(args):
        return None
    return str(args[index + 1])


def _weights_label(path: str | None) -> str | None:
    if not path:
        return None
    file = Path(path)
    if not file.exists():
        return None
    folder = file.parent
    parts = list(folder.glob("*.gguf"))
    total = sum(item.stat().st_size for item in parts) if len(parts) > 1 else file.stat().st_size
    if total >= 1_000_000_000:
        value = total / 1_000_000_000
        text = f"{value:.0f}" if value == int(value) else f"{value:.1f}"
        return f"{text} GB"
    return f"{total / 1_000_000:.0f} MB"


def _installed_rows(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in data:
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        status = item.get("status") if isinstance(item.get("status"), dict) else {}
        args = status.get("args") if isinstance(status.get("args"), list) else []
        context_raw = _arg(args, "--ctx-size")
        modalities = []
        architecture = item.get("architecture")
        if isinstance(architecture, dict):
            modalities = architecture.get("input_modalities") or []
        state = str(status.get("value") or "unloaded")
        job = _load_jobs.get(model_id)
        error = None
        if job == "loading":
            state = "loading"
        elif job:
            state = "failed"
            error = job
        rows.append(
            {
                "id": model_id,
                "context": int(context_raw) if context_raw and context_raw.isdigit() else None,
                "size": _weights_label(_arg(args, "--model")),
                "vision": "image" in modalities,
                "state": state,
                "error": error,
            }
        )
    return sorted(rows, key=lambda row: row["id"])


def list_models() -> list[str] | None:
    """Return model ids when Llama is serving, or None when it is down."""
    data = _models_payload()
    if data is None:
        return None
    return [row["id"] for row in _installed_rows(data)]


def status() -> dict[str, Any]:
    models = list_models()
    running = models is not None
    with _lock:
        if _state["phase"] == "updating":
            phase = "updating"
            detail = _state["detail"]
        else:
            phase = "ready" if running else _state["phase"]
            detail = "" if running else _state["detail"]
            if running:
                _state["phase"] = "ready"
                _state["detail"] = ""
    return {
        "baseUrl": LLAMA_BASE_URL,
        "installed": bool(llama_binary()) or app_installed(),
        "running": running,
        "version": _llama_version() if running else None,
        "models": models or [],
        "phase": phase,
        "detail": detail,
        "debug": _debug_public() if phase == "error" else {},
    }


def _llama_version() -> str | None:
    binary = llama_binary()
    if not binary:
        return None
    try:
        completed = subprocess.run(
            [binary, "version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = (completed.stdout or completed.stderr or "").strip().splitlines()
    return line[0] if line else None


def _set(phase: str, detail: str = "", debug: dict[str, Any] | None = None) -> None:
    global _debug
    with _lock:
        _state["phase"] = phase
        _state["detail"] = detail
        if debug is not None:
            _debug = debug
        elif phase != "error":
            _debug = {}


def _debug_public() -> dict[str, Any]:
    with _lock:
        payload = dict(_debug)
        if _serve_log and not payload.get("log"):
            payload["log"] = "\n".join(_serve_log)
        return payload


def _clip(text: str, limit: int = 40) -> str:
    lines = [line.rstrip() for line in (text or "").splitlines() if line.strip()]
    return "\n".join(lines[-limit:])


def _binary_candidates() -> list[str]:
    home = Path.home()
    return [
        str(home / ".local" / "bin" / "llama"),
        str(home / ".llama-app" / "llama"),
        "/Applications/Llama.app/Contents/MacOS/llama",
        "/Applications/Llama.app/Contents/Resources/llama",
        str(home / "Applications" / "Llama.app" / "Contents" / "MacOS" / "llama"),
    ]


def _install_debug(
    *,
    command: str,
    exit_code: int | None,
    binary: str | None,
    log: str,
) -> dict[str, Any]:
    return {
        "command": command,
        "exitCode": exit_code,
        "port": _SERVE_PORT,
        "binary": binary,
        "searched": _binary_candidates(),
        "log": _clip(log),
    }


def llama_binary() -> str | None:
    """The llama.cpp CLI. Prefer the copy the installer writes, then PATH."""
    candidates = [Path(item) for item in _binary_candidates()]
    which = shutil.which("llama")
    if which:
        candidates.append(Path(which))
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


_serve_proc: subprocess.Popen[bytes] | None = None


def serve_pid() -> int | None:
    """Pid of the llama serve process Sandwalk started, if it is still alive."""
    proc = _serve_proc
    if proc is None or proc.poll() is not None:
        return None
    return proc.pid


def _capture_serve(proc: subprocess.Popen[bytes], command: list[str]) -> None:
    stream = getattr(proc, "stderr", None)
    if stream is not None:
        for raw in iter(stream.readline, b""):
            line = raw.decode("utf-8", errors="replace").rstrip()
            if not line:
                continue
            with _lock:
                _serve_log.append(line)
    code = proc.poll()
    if code in (None, 0) or list_models() is not None:
        return
    with _lock:
        log = "\n".join(_serve_log)
    _set(
        "error",
        f"llama serve exited {code}.",
        debug=_install_debug(
            command=" ".join(command),
            exit_code=code,
            binary=command[0] if command else None,
            log=log,
        ),
    )


def _start_serve(binary: str) -> None:
    """Run `llama serve` ourselves. Do not launch the menu-bar app."""
    global _serve_proc, _serve_command
    if _serve_proc is not None and _serve_proc.poll() is None:
        return
    command = [binary, "serve", "--host", "127.0.0.1", "--port", str(_SERVE_PORT)]
    _serve_command = command
    with _lock:
        _serve_log.clear()
    _serve_proc = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    threading.Thread(
        target=_capture_serve,
        args=(_serve_proc, command),
        name="llama-serve-log",
        daemon=True,
    ).start()


def _install_cli_then_serve() -> None:
    """Install the llama CLI. The Homebrew cask only drops the menu-bar app."""
    command = f"curl -LsSf {_INSTALL_URL} | sh"
    curl = shutil.which("curl")
    if not curl:
        _set(
            "error",
            "curl is not available, so Sandwalk cannot install the llama CLI.",
            debug=_install_debug(command=command, exit_code=None, binary=None, log=""),
        )
        return
    _set("installing", "Installing the llama CLI…")
    script = Path(tempfile.gettempdir()) / "sandwalk-llama-install.sh"
    try:
        download = subprocess.run(
            [curl, "-LsSf", _INSTALL_URL, "-o", str(script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if download.returncode != 0:
            log = (download.stderr or download.stdout or "").strip()
            _set(
                "error",
                _clip(log, 1) or f"Could not download the llama installer ({download.returncode}).",
                debug=_install_debug(
                    command=command,
                    exit_code=download.returncode,
                    binary=None,
                    log=log,
                ),
            )
            return
        env = os.environ.copy()
        local_bin = str(Path.home() / ".local" / "bin")
        env["PATH"] = local_bin + os.pathsep + env.get("PATH", "")
        completed = subprocess.run(
            ["/bin/sh", str(script)],
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        _set(
            "error",
            f"Could not install the llama CLI ({exc}).",
            debug=_install_debug(command=command, exit_code=None, binary=None, log=str(exc)),
        )
        return
    finally:
        try:
            script.unlink(missing_ok=True)
        except OSError:
            pass
    binary = llama_binary()
    log = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    if completed.returncode != 0 or not binary:
        lines = [line for line in log.splitlines() if line.strip()]
        if completed.returncode != 0 and lines:
            detail = lines[-1]
        elif not binary:
            detail = "The llama CLI did not appear after install."
        else:
            detail = f"llama installer exited {completed.returncode}"
        _set(
            "error",
            detail,
            debug=_install_debug(
                command=command,
                exit_code=completed.returncode,
                binary=binary,
                log=log,
            ),
        )
        return
    _set("opening", "Starting llama serve on port 9931…")
    _start_serve(binary)


def _memory_bytes() -> int:
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page = os.sysconf("SC_PAGE_SIZE")
        return int(pages) * int(page)
    except (ValueError, OSError, AttributeError):
        return 16 * 1000**3


def _fits(size_bytes: int, memory: int) -> bool:
    if size_bytes <= 0:
        return True
    # Leave room for the system and the KV cache. The catalog sizes are weights.
    return size_bytes <= int(memory * 0.6)


def publish_profile() -> None:
    """Keep a Llama profile saved so the model list can discover the running server."""
    if list_models() is None:
        return
    from agent.config import Config
    from agent_server.models.model_profiles import UpsertModelProfileRequest
    from agent_server.models_service.profiles import upsert_profile

    upsert_profile(
        Config.load(),
        UpsertModelProfileRequest(
            id="llama_local",
            label="Llama",
            backend="llama",
            base_url=LLAMA_BASE_URL,
            discovery=["v1_models"],
        ),
    )


def catalog(query: str = "") -> dict[str, Any]:
    """Installed models plus llama.app's featured picks that fit this Mac."""
    payload = _models_payload()
    if payload is None:
        installed_rows = [
            {
                "id": model_id,
                "context": None,
                "size": None,
                "vision": False,
                "state": "unloaded",
                "error": None,
            }
            for model_id in (list_models() or [])
        ]
    else:
        installed_rows = _installed_rows(payload)
    installed_bases = {row["id"].split(":", 1)[0] for row in installed_rows}
    needle = query.strip().lower()
    try:
        response = httpx.get(_CATALOG_URL, timeout=20.0)
        response.raise_for_status()
        families = response.json()
    except (httpx.HTTPError, ValueError):
        families = []
    if not isinstance(families, list):
        families = []

    memory = _memory_bytes()
    recommended: list[dict[str, Any]] = []
    for family in families:
        if not isinstance(family, dict):
            continue
        featured = bool(family.get("featured"))
        brand = str(family.get("brand") or "")
        for size in family.get("sizes") or []:
            if not isinstance(size, dict):
                continue
            builds = [item for item in (size.get("builds") or []) if isinstance(item, dict) and item.get("repo")]
            fitting = [item for item in builds if _fits(int(item.get("sizeBytes") or 0), memory)]
            pool = fitting or ([] if featured else builds)
            if not pool:
                continue
            best = max(pool, key=lambda item: int(item.get("sizeBytes") or 0))
            repo = str(best.get("repo") or "")
            quant = str(best.get("quant") or "") or None
            row = {
                "id": f"{repo}:{quant}" if quant else repo,
                "name": str(size.get("name") or repo),
                "brand": brand,
                "repo": repo,
                "quant": quant,
                "size": str(best.get("size") or "") or None,
                "vision": bool(size.get("vision")),
                "installed": repo in installed_bases,
            }
            blob = f"{row['name']} {brand} {repo} {row['quant'] or ''}".lower()
            if needle:
                if needle in blob:
                    recommended.append(row)
                continue
            if featured and fitting:
                recommended.append(row)
    return {"installed": installed_rows, "recommended": recommended}


def _download(binary: str, spec: str) -> None:
    _set("installing", f"Downloading {spec}…")
    try:
        completed = subprocess.run(
            [binary, "download", "-hf", spec],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        _set("error", f"Could not run llama download ({exc}).")
        return
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()
        _set("error", tail[-1] if tail else f"llama download exited {completed.returncode}")
        return
    _set("ready", "")


_CONTEXT_TIERS = (4096, 8192, 16384, 32768, 65536, 131072)


def _write_ctx(path: Path, model_id: str, ctx: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines()
    header = f"[{model_id}]"
    start = next((i for i, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend([header, f"ctx-size = {ctx}"])
    else:
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].startswith("[")),
            len(lines),
        )
        replaced = False
        for i in range(start + 1, end):
            if lines[i].strip().startswith("ctx-size"):
                lines[i] = f"ctx-size = {ctx}"
                replaced = True
                break
        if not replaced:
            lines.insert(end, f"ctx-size = {ctx}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


_mem_cache: dict[str, list[dict[str, Any]]] = {}


def _parse_fitp(output: str) -> int | None:
    total = 0
    rows = 0
    for line in output.splitlines():
        tokens = line.split()
        if len(tokens) != 4:
            continue
        try:
            numbers = [int(token) for token in tokens[1:]]
        except ValueError:
            continue
        if tokens[0].lstrip("-").isdigit():
            continue
        total += sum(numbers)
        rows += 1
    return total if rows else None


def _format_memory(mib: float) -> str:
    gb = mib / 1024
    rounded = round(gb, 1)
    text = f"{rounded:.0f}" if rounded == int(rounded) else f"{rounded:.1f}"
    return f"{text} GB"


def _model_path(model_id: str) -> str | None:
    for item in _models_payload() or []:
        if str(item.get("id") or "") != model_id:
            continue
        status = item.get("status") if isinstance(item.get("status"), dict) else {}
        args = status.get("args") if isinstance(status.get("args"), list) else []
        return _arg(args, "--model")
    return None


def _probe_mib(binary: str, path: str, ctx: int) -> int | None:
    try:
        completed = subprocess.run(
            [binary, "fit-params", "-m", path, "-c", str(ctx), "-fitp", "on"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    return _parse_fitp(completed.stdout)


def memory_tiers(model_id: str) -> dict[str, Any]:
    """Memory at each context length, using the same two-point fit as Llama.app."""
    cleaned = model_id.strip()
    cached = _mem_cache.get(cleaned)
    if cached is not None:
        return {"tiers": cached}
    binary = llama_binary()
    path = _model_path(cleaned)
    if not binary or not path:
        return {"tiers": []}
    low = _probe_mib(binary, path, 4096)
    high = _probe_mib(binary, path, 131072)
    if low is None or high is None or high < low:
        return {"tiers": []}
    per_token = (high - low) / (131072 - 4096)
    intercept = low - per_token * 4096
    tiers = [
        {
            "context": ctx,
            "memory": _format_memory(max(intercept, 0) + per_token * ctx),
        }
        for ctx in _CONTEXT_TIERS
    ]
    _mem_cache[cleaned] = tiers
    return {"tiers": tiers}


def set_context(model_id: str, ctx: int) -> dict[str, Any]:
    """Pin ctx-size for one model. Applies the next time that model loads."""
    cleaned = model_id.strip()
    if not cleaned or "/" not in cleaned:
        raise ValueError("Model id is required.")
    if ctx not in _CONTEXT_TIERS:
        raise ValueError("Context must be 4k, 8k, 16k, 32k, 64k, or 128k.")
    _write_ctx(Path.home() / ".config" / "llama" / "models.user.ini", cleaned, ctx)
    preset = Path.home() / "Library" / "Application Support" / "Llama" / "models.ini"
    if preset.exists():
        _write_ctx(preset, cleaned, ctx)
    # The router keeps the context it loaded with. Drop the model so the
    # next request starts it from the updated preset.
    try:
        # The router reads models.ini once. This asks it to re-read and drop
        # any model whose preset changed, so the next load uses the new context.
        httpx.get("http://127.0.0.1:9931/models", params={"reload": "1"}, timeout=15)
    except httpx.HTTPError:
        pass
    return {"ok": True, "model": cleaned, "context": ctx}


def _router(path: str, model_id: str, timeout: float) -> None:
    response = httpx.post(
        f"http://127.0.0.1:9931{path}",
        json={"model": model_id},
        timeout=timeout,
    )
    response.raise_for_status()


def _load(model_id: str) -> None:
    with _lock:
        _load_jobs[model_id] = "loading"
    try:
        _router("/models/load", model_id, 600)
    except (httpx.HTTPError, ValueError) as exc:
        with _lock:
            _load_jobs[model_id] = str(exc)
        return
    with _lock:
        _load_jobs.pop(model_id, None)


def update_engine() -> dict[str, Any]:
    """Download the newest llama CLI. The running server keeps the old build until Llama restarts."""
    binary = llama_binary()
    if not binary:
        raise ValueError("The llama CLI is not installed.")

    def run() -> None:
        _set("updating", "Updating llama…")
        try:
            completed = subprocess.run(
                [binary, "update"],
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            _set("error", f"Could not update llama ({exc}).")
            return
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout or "").strip().splitlines()
            _set("error", tail[-1] if tail else f"llama update exited {completed.returncode}")
            return
        version = _llama_version() or "the latest build"
        _set(
            "ready",
            f"Updated to {version}. Quit Llama and open it again so this engine is the one serving.",
        )

    with _lock:
        if _state["phase"] == "updating":
            return status()
    threading.Thread(target=run, name="llama-update", daemon=True).start()
    return status()


def load_model(model_id: str) -> dict[str, Any]:
    """Ask llama.cpp to load this model now. Returns immediately; the row polls."""
    cleaned = model_id.strip()
    if not cleaned:
        raise ValueError("Model id is required.")
    threading.Thread(target=_load, args=(cleaned,), name="llama-load", daemon=True).start()
    return {"ok": True, "state": "loading"}


def unload_model(model_id: str) -> dict[str, Any]:
    cleaned = model_id.strip()
    if not cleaned:
        raise ValueError("Model id is required.")
    _router("/models/unload", cleaned, 60)
    with _lock:
        _load_jobs.pop(cleaned, None)
    return {"ok": True, "state": "unloaded"}


def install_model(repo: str, quant: str | None = None) -> dict[str, Any]:
    """Download a GGUF with `llama download`. The running server picks it up from the Hugging Face cache."""
    cleaned = repo.strip()
    if cleaned.count("/") != 1:
        raise ValueError("Model repo must look like org/name.")
    binary = llama_binary()
    if not binary:
        raise ValueError("The llama CLI is not installed.")
    spec = f"{cleaned}:{quant.strip()}" if quant and quant.strip() else cleaned
    threading.Thread(
        target=_download,
        args=(binary, spec),
        name="llama-download",
        daemon=True,
    ).start()
    return {"ok": True, "spec": spec}


def ensure() -> dict[str, Any]:
    """Start Llama if it is down. Install the cask first when the app is missing."""
    current = status()
    if current["running"]:
        return current
    with _lock:
        busy = _state["phase"] in {"installing", "opening"}
    if busy:
        return status()
    binary = llama_binary()
    if binary:
        _set("opening", "Starting llama serve on port 9931…")
        _start_serve(binary)
        return status()
    thread = threading.Thread(target=_install_cli_then_serve, name="llama-runtime", daemon=True)
    thread.start()
    return status()
