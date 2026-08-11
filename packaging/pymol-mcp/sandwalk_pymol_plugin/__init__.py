# pyright: reportMissingImports=false
"""
Sandwalk PyMOL MCP plugin: TCP server that accepts framed JSON requests from
the `agentic_pymol` MCP server, gates them on a shared-secret token, and
dispatches to PyMOL's `cmd.*` API.

Vendored/adapted from Arcadia-Science/agentic-pymol for Plugin Manager zip
install (commercial + open-source). Kept as one package with `__init__.py` +
`plugin.ui` so URL/zip install is reliable.

Sections:

    SERIALIZE — JSON-friendly conversion of PyMOL return values
    FRAMING   — length-prefixed wire protocol
    AUTH      — shared-secret token load / create / verify
    HANDLERS  — op dispatch (call / iterate / exec / interrupt)
    SERVER    — accept loop + per-connection worker
    PLUGIN    — PyMOL Plugin Manager hooks (menu, dialog, start/stop)
    SETUP     — sandwalk-pymol setup/doctor (managed MCP launcher)
"""

from __future__ import annotations
import hmac
import io
import json
import logging
import math
import os
import re
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import threading
import traceback
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Module-level constants and globals
# ─────────────────────────────────────────────────────────────────────────────

MAX_MESSAGE_BYTES = 4 * 1024 * 1024
LENGTH_HEADER = struct.Struct(">I")

TOKEN_PATH = Path.home() / ".config" / "pymol-mcp" / "token"
TOKEN_BYTES = 32

ITERATE_ROW_LIMIT = 200_000
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")

DEFAULT_PORT = 9877

PLUGIN_VERSION = "0.0.1"

SANDWALK_HOME = Path.home() / ".sandwalk"
PYMOL_MCP_HOME = SANDWALK_HOME / "pymol-mcp"
PYMOL_MCP_VENV = PYMOL_MCP_HOME / "venv"
PYMOL_MCP_BIN = PYMOL_MCP_HOME / "bin"
PYMOL_MCP_LAUNCHER = PYMOL_MCP_BIN / "agentic-pymol"
PLUGIN_ZIP_URL = "https://sandwalk.sh/pymol/plugin.zip"
# Bundled with the plugin zip (and mirrored under sandwalk CLI vendor/).
_VENDOR_PACKAGE = Path(__file__).resolve().parent / "vendor" / "agentic-pymol"

logger = logging.getLogger("pymol-mcp-plugin")
_token: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# SERIALIZE
# ─────────────────────────────────────────────────────────────────────────────


def serialize(value: Any) -> Any:
    """
    Convert a PyMOL return value into a JSON-friendly shape.

    Non-finite floats (NaN, +/-inf) are coerced to `None` so the resulting
    payload is strict JSON: Python's `json.dumps` would otherwise emit the
    non-standard `NaN` / `Infinity` tokens, which most strict parsers reject.
    The coercion applies recursively to floats inside lists, dicts, ndarray
    data, and atom fields.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    if isinstance(value, dict):
        return {str(k): serialize(v) for k, v in value.items()}
    np = _maybe_numpy()
    if np is not None and isinstance(value, np.ndarray):
        return {
            "_kind": "ndarray",
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "data": serialize(value.tolist()),
        }
    indexed_cls = _maybe_chempy_indexed()
    if indexed_cls is not None and isinstance(value, indexed_cls):
        return {
            "_kind": "model",
            "atoms": [_serialize_atom(a) for a in value.atom],
            "n_atoms": len(value.atom),
        }
    return {"_kind": "repr", "value": repr(value)[:2000]}


def _serialize_atom(atom: Any) -> dict[str, Any]:
    fields = (
        "name",
        "resn",
        "resi",
        "chain",
        "segi",
        "elem",
        "ss",
        "b",
        "q",
        "vdw",
        "partial_charge",
        "formal_charge",
        "index",
        "id",
    )
    out: dict[str, Any] = {}
    for f in fields:
        if hasattr(atom, f):
            out[f] = serialize(getattr(atom, f))
    if hasattr(atom, "coord"):
        out["coord"] = serialize(list(atom.coord))
    return out


def _maybe_numpy():
    try:
        import numpy

        return numpy
    except ImportError:
        return None


def _maybe_chempy_indexed():
    try:
        from chempy import Indexed

        return Indexed
    except ImportError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# FRAMING
# ─────────────────────────────────────────────────────────────────────────────


def recv_exactly(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed during recv")
        buf.extend(chunk)
    return bytes(buf)


def recv_message(sock: socket.socket) -> dict[str, Any]:
    header = recv_exactly(sock, LENGTH_HEADER.size)
    (length,) = LENGTH_HEADER.unpack(header)
    if length > MAX_MESSAGE_BYTES:
        raise ValueError(f"message length {length} exceeds {MAX_MESSAGE_BYTES} byte cap")
    body = recv_exactly(sock, length)
    return json.loads(body.decode("utf-8"))


def send_message(sock: socket.socket, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    if len(body) > MAX_MESSAGE_BYTES:
        body = json.dumps(
            {
                "ok": False,
                "error": {
                    "type": "ResponseTooLarge",
                    "message": f"response of {len(body)} bytes exceeds {MAX_MESSAGE_BYTES} cap",
                    "traceback": "",
                },
                "stdout": "",
            }
        ).encode("utf-8")
    sock.sendall(LENGTH_HEADER.pack(len(body)) + body)


# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────


def _load_or_create_token() -> str:
    env = os.environ.get("PYMOL_MCP_TOKEN", "").strip()
    if env:
        return env
    if TOKEN_PATH.exists():
        existing = TOKEN_PATH.read_text().strip()
        if existing:
            return existing
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(TOKEN_BYTES)
    TOKEN_PATH.write_text(token)
    TOKEN_PATH.chmod(0o600)
    logger.info(f"PyMOL MCP: generated new shared-secret token at {TOKEN_PATH}")
    return token


def get_token() -> str:
    global _token
    if _token is None:
        _token = _load_or_create_token()
    return _token


def token_ok(presented: Any) -> bool:
    if not isinstance(presented, str):
        return False
    return hmac.compare_digest(presented, get_token())


# ─────────────────────────────────────────────────────────────────────────────
# HANDLERS
# ─────────────────────────────────────────────────────────────────────────────


def dispatch(request: dict[str, Any]) -> dict[str, Any]:
    if not token_ok(request.get("token")):
        return _error_response("Unauthorized", "missing or invalid auth token", "", "")
    op = request.get("op")
    if op == "call":
        return _handle_call(request)
    if op == "iterate":
        return _handle_iterate(request)
    if op == "exec":
        return _handle_exec(request)
    if op == "interrupt":
        return _handle_interrupt(request)
    return _error_response("BadRequest", f"unknown op: {op!r}", "", "")


def _handle_interrupt(request: dict[str, Any]) -> dict[str, Any]:
    from pymol import cmd

    logger.info("PyMOL MCP interrupt requested")
    cmd.interrupt()
    return {"ok": True, "value": None, "stdout": ""}


def _handle_call(request: dict[str, Any]) -> dict[str, Any]:
    fn_name = request.get("fn", "")
    args = request.get("args", []) or []
    kwargs = request.get("kwargs", {}) or {}
    if not isinstance(fn_name, str) or not fn_name:
        return _error_response("BadRequest", "fn must be a non-empty string", "", "")
    from pymol import cmd

    target: Any = cmd
    for part in fn_name.split("."):
        if not IDENTIFIER_RE.match(part):
            return _error_response("BadRequest", f"invalid attribute name: {part!r}", "", "")
        if not hasattr(target, part):
            return _error_response("AttributeError", f"cmd has no attribute {fn_name!r}", "", "")
        target = getattr(target, part)
    if not callable(target):
        return _error_response("TypeError", f"{fn_name!r} is not callable", "", "")
    logger.info(f"PyMOL MCP call: {fn_name}(args={args!r}, kwargs={kwargs!r})")
    return _run_capturing(lambda: target(*args, **kwargs))


def _handle_iterate(request: dict[str, Any]) -> dict[str, Any]:
    selection = request.get("selection", "")
    properties = request.get("properties", []) or []
    state = request.get("state")
    if not isinstance(selection, str):
        return _error_response("BadRequest", "selection must be a string", "", "")
    if not isinstance(properties, list) or not all(isinstance(p, str) for p in properties):
        return _error_response("BadRequest", "properties must be a list of strings", "", "")
    for p in properties:
        if not IDENTIFIER_RE.match(p):
            return _error_response("BadRequest", f"invalid property identifier: {p!r}", "", "")
    if not properties:
        return _error_response("BadRequest", "properties must not be empty", "", "")
    if not isinstance(state, int) or isinstance(state, bool):
        return _error_response("BadRequest", "state must be an int", "", "")

    from pymol import cmd

    payload = "{" + ", ".join(f'"{p}": {p}' for p in properties) + "}"
    expression = (
        f"(_acc.append({payload}) if len(_acc) < {ITERATE_ROW_LIMIT} else _overflow.append(1))"
    )
    space: dict[str, Any] = {"_acc": [], "_overflow": []}

    def thunk():
        return cmd.iterate_state(state, selection, expression, space=space)

    logger.info(
        f"PyMOL MCP iterate: selection={selection!r}, properties={properties!r}, state={state!r}"
    )
    result = _run_capturing(thunk)
    if not result["ok"]:
        return result
    if space["_overflow"]:
        return _error_response(
            "IterateOverflow",
            f"iterate produced more than {ITERATE_ROW_LIMIT} rows; narrow the selection",
            "",
            result["stdout"],
        )
    return {
        "ok": True,
        "value": [serialize(row) for row in space["_acc"]],
        "stdout": result["stdout"],
    }


def _handle_exec(request: dict[str, Any]) -> dict[str, Any]:
    """
    Run arbitrary Python in the plugin's interpreter and (optionally) eval a
    return expression. Intentionally unsandboxed: callers can import anything,
    touch the filesystem, and make network calls. Gated only by the
    shared-secret token validated upstream in `dispatch`; the listening socket
    is bound to 127.0.0.1 so it is not reachable off-host without explicit
    forwarding.
    """
    code = request.get("code", "")
    return_expr = request.get("return_expr")
    if not isinstance(code, str):
        return _error_response("BadRequest", "code must be a string", "", "")
    if return_expr is not None and not isinstance(return_expr, str):
        return _error_response("BadRequest", "return_expr must be a string or null", "", "")
    import pymol
    from pymol import cmd

    exec_globals: dict[str, Any] = {
        "cmd": cmd,
        "pymol": pymol,
        "__builtins__": __builtins__,
    }
    np = _maybe_numpy()
    if np is not None:
        exec_globals["np"] = np
    logger.info(f"PyMOL MCP exec ({len(code)} chars, return_expr={return_expr!r})")

    def thunk():
        exec(code, exec_globals)
        if return_expr is None:
            return None
        return eval(return_expr, exec_globals)

    return _run_capturing(thunk)


def _run_capturing(thunk) -> dict[str, Any]:
    buffer = io.StringIO()
    try:
        with redirect_stdout(buffer):
            value = thunk()
    except Exception as e:
        return _error_response(
            type(e).__name__,
            str(e),
            traceback.format_exc(),
            buffer.getvalue(),
        )
    return {
        "ok": True,
        "value": serialize(value),
        "stdout": buffer.getvalue(),
    }


def _error_response(error_type: str, message: str, tb: str, stdout: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"type": error_type, "message": message, "traceback": tb},
        "stdout": stdout,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SERVER
# ─────────────────────────────────────────────────────────────────────────────


class SocketServer:
    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.socket: socket.socket | None = None
        self.running = False
        self.thread: threading.Thread | None = None

    def start(self) -> bool:
        if self.running:
            return False
        get_token()
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(2.0)
        if self.socket:
            try:
                self.socket.close()
            except OSError:
                pass
        self.socket = None
        self.thread = None

    def _run(self) -> None:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(4)
            self.socket.settimeout(0.1)
            logger.info(f"PyMOL MCP socket server listening on {self.host}:{self.port}")
            while self.running:
                try:
                    client, address = self.socket.accept()
                except TimeoutError:
                    continue
                except OSError as e:
                    logger.info(f"accept error: {e}")
                    break
                logger.info(f"PyMOL MCP client connected: {address}")
                threading.Thread(target=self._serve_client, args=(client,), daemon=True).start()
        except Exception as e:
            logger.info(f"PyMOL MCP socket server error: {e}")
            traceback.print_exc()
        finally:
            if self.socket:
                try:
                    self.socket.close()
                except OSError:
                    pass
            logger.info("PyMOL MCP socket server stopped")

    def _serve_client(self, client: socket.socket) -> None:
        client.settimeout(None)
        try:
            while self.running:
                request = recv_message(client)
                response = dispatch(request)
                send_message(client, response)
        except (ConnectionError, OSError) as e:
            logger.info(f"PyMOL MCP client disconnected: {e}")
        except Exception as e:
            logger.info(f"PyMOL MCP client handler crashed: {e}")
            traceback.print_exc()
        finally:
            try:
                client.close()
            except OSError:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# PLUGIN (PyMOL menu / dialog hooks)
# ─────────────────────────────────────────────────────────────────────────────

dialog: Any = None
socket_server: SocketServer | None = None
listening: bool = False
current_port: int = DEFAULT_PORT


def __init_plugin__(app: Any = None) -> None:  # noqa: ARG001 -- PyMOL passes the app arg
    from pymol import cmd
    from pymol.plugins import addmenuitemqt

    addmenuitemqt("Sandwalk PyMOL MCP", run_plugin_gui)
    cmd.extend("sandwalk-pymol", _sandwalk_pymol_command)
    cmd.extend("sandwalk_pymol", _sandwalk_pymol_command)


def run_plugin_gui() -> None:
    global dialog
    if dialog is None:
        dialog = make_dialog()
    dialog.show()


def make_dialog() -> Any:
    from pymol.Qt import QtWidgets
    from pymol.Qt.utils import loadUi

    dlg = QtWidgets.QDialog()
    uifile = Path(__file__).parent / "plugin.ui"
    form = loadUi(uifile, dlg)
    form.input_port.setValue(current_port)
    _set_status(form, "Not listening")

    def toggle_listening() -> None:
        global socket_server, listening, current_port
        if not listening:
            current_port = form.input_port.value()
            socket_server = SocketServer(port=current_port)
            if socket_server.start():
                listening = True
                form.button_toggle_listening.setText("Stop Listening")
                _set_status(form, f"Listening on port {current_port}")
        else:
            if socket_server:
                socket_server.stop()
            listening = False
            form.button_toggle_listening.setText("Start Listening")
            _set_status(form, "Not listening")

    def close_dialog() -> None:
        global socket_server, listening
        if socket_server and listening:
            socket_server.stop()
            listening = False
        dlg.close()

    form.button_toggle_listening.clicked.connect(toggle_listening)
    form.button_close.clicked.connect(close_dialog)
    return dlg


def _set_status(form: Any, text: str) -> None:
    form.label_status.setText(text)
    if "Not listening" in text:
        form.label_status.setStyleSheet("color: red;")
    elif "Listening" in text:
        form.label_status.setStyleSheet("color: green;")
    else:
        form.label_status.setStyleSheet("")


# ─────────────────────────────────────────────────────────────────────────────
# SETUP (Sandwalk managed MCP launcher)
# ─────────────────────────────────────────────────────────────────────────────


def _sandwalk_pymol_command(arg: str = "") -> None:
    tokens = [t for t in str(arg or "").strip().split() if t]
    verb = (tokens[0].lower() if tokens else "help")
    rest = tokens[1:]
    if verb in {"help", "-h", "--help"}:
        _print_sandwalk_help()
        return
    if verb == "setup":
        _sandwalk_setup()
        return
    if verb == "doctor":
        _sandwalk_doctor()
        return
    print(f"Unknown sandwalk-pymol command '{verb}'. Try: sandwalk-pymol help")


def _print_sandwalk_help() -> None:
    print(
        "\n".join(
            [
                f"Sandwalk PyMOL MCP v{PLUGIN_VERSION}",
                "  sandwalk-pymol setup   Install managed agentic-pymol launcher",
                "  sandwalk-pymol doctor  Check launcher, token, listening",
                "",
                f"Plugin zip: {PLUGIN_ZIP_URL}",
                f"Launcher:   {PYMOL_MCP_LAUNCHER}",
                "",
                "Then in Sandwalk: enable PyMOL MCP, or run:",
                "  sandwalk mcp install pymol",
            ]
        )
    )


def _find_host_python() -> str | None:
    candidates = [
        shutil.which("python3"),
        shutil.which("python"),
        "/usr/bin/python3",
        "/usr/local/bin/python3",
        str(Path(sys.executable)) if sys.executable else "",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _sandwalk_setup() -> None:
    print("\nSandwalk PyMOL MCP: installing managed launcher…")
    host_python = _find_host_python()
    if not host_python:
        print("Error: could not find a host python3 to create the venv.")
        print("Install Python 3.10+ and retry: sandwalk-pymol setup")
        return

    if not (_VENDOR_PACKAGE / "pyproject.toml").is_file():
        print(f"Error: vendored agentic-pymol missing at {_VENDOR_PACKAGE}")
        print("Re-download the plugin zip from https://sandwalk.sh/pymol/plugin.zip")
        print("Or run: sandwalk mcp install pymol")
        return

    PYMOL_MCP_HOME.mkdir(parents=True, exist_ok=True)
    PYMOL_MCP_BIN.mkdir(parents=True, exist_ok=True)

    uv = shutil.which("uv")
    if uv:
        print(f"Using uv ({uv})")
        create = _run([uv, "venv", str(PYMOL_MCP_VENV)])
        if create.returncode != 0:
            print(create.stdout.strip())
            print(create.stderr.strip())
            print("uv venv failed; falling back to python -m venv")
            uv = None
        else:
            install = _run(
                [
                    uv,
                    "pip",
                    "install",
                    "--python",
                    str(PYMOL_MCP_VENV),
                    str(_VENDOR_PACKAGE),
                ]
            )
            if install.returncode != 0:
                print(install.stdout.strip())
                print(install.stderr.strip())
                print("Error: failed to install vendored agentic-pymol with uv.")
                return
    if not uv:
        print(f"Using {host_python} -m venv")
        if not PYMOL_MCP_VENV.exists():
            create = _run([host_python, "-m", "venv", str(PYMOL_MCP_VENV)])
            if create.returncode != 0:
                print(create.stdout.strip())
                print(create.stderr.strip())
                print("Error: failed to create venv.")
                return
        pip = PYMOL_MCP_VENV / "bin" / "pip"
        if not pip.is_file():
            pip = PYMOL_MCP_VENV / "Scripts" / "pip.exe"
        install = _run(
            [
                str(pip),
                "install",
                "--upgrade",
                "pip",
                str(_VENDOR_PACKAGE),
            ]
        )
        if install.returncode != 0:
            print(install.stdout.strip())
            print(install.stderr.strip())
            print("Error: failed to install vendored agentic-pymol.")
            return

    venv_bin = PYMOL_MCP_VENV / "bin" / "agentic-pymol"
    if not venv_bin.is_file():
        venv_bin = PYMOL_MCP_VENV / "Scripts" / "agentic-pymol.exe"
    if not venv_bin.is_file():
        print(f"Error: expected launcher missing at {venv_bin}")
        return

    if PYMOL_MCP_LAUNCHER.exists() or PYMOL_MCP_LAUNCHER.is_symlink():
        PYMOL_MCP_LAUNCHER.unlink()
    try:
        PYMOL_MCP_LAUNCHER.symlink_to(venv_bin)
    except OSError:
        # Windows / no symlink privilege — write a small shim instead.
        PYMOL_MCP_LAUNCHER.write_text(
            "#!/usr/bin/env bash\n"
            f'exec "{venv_bin}" "$@"\n',
            encoding="utf-8",
        )
        PYMOL_MCP_LAUNCHER.chmod(0o755)

    print("\nSandwalk PyMOL MCP: setup complete.")
    print(f"  Launcher: {PYMOL_MCP_LAUNCHER}")
    print("Next:")
    print("  1. Click Start Listening in this plugin")
    print("  2. In Sandwalk: enable PyMOL MCP, or run:")
    print("       sandwalk mcp install pymol")


def _sandwalk_doctor() -> None:
    print("\nSandwalk PyMOL MCP doctor:")
    launcher_ok = PYMOL_MCP_LAUNCHER.is_file() or PYMOL_MCP_LAUNCHER.is_symlink()
    print(f"  [{'OK' if launcher_ok else 'MISSING'}] launcher {PYMOL_MCP_LAUNCHER}")
    token_ok = TOKEN_PATH.is_file() and bool(TOKEN_PATH.read_text().strip())
    print(f"  [{'OK' if token_ok else 'MISSING'}] token {TOKEN_PATH}")
    print(f"  [{'OK' if listening else 'OFF'}] listening on port {current_port}")
    if not launcher_ok:
        print("\nFix: run  sandwalk-pymol setup")
    if not token_ok or not listening:
        print("Fix: open this plugin and click Start Listening")
    if launcher_ok and token_ok:
        print("\nIn Sandwalk: sandwalk mcp install pymol  (or Enable on the MCP page)")
