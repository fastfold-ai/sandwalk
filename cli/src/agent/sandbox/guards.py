"""Import/file/subprocess guards used to sandbox generated Python code."""

from pathlib import Path

from agent.config import CONFIG_DIR


def configure_matplotlib() -> None:
    """Force Agg before pyplot import. Lazy so agent startup can report a clear miss."""
    import matplotlib

    matplotlib.use("Agg")


# Modules blocked from import inside the sandbox
BLOCKED_MODULES = frozenset({
    "subprocess", "shutil", "socket", "http.server", "smtplib",
    "ctypes",
})

# Allow os import but we'll provide a safe subset in namespace
SAFE_OS_ATTRS = frozenset({
    "path", "listdir", "walk", "getcwd", "sep", "linesep",
    "stat", "fstat", "scandir", "DirEntry",
})


def make_safe_import(real_import):
    """Wrap __import__ to block dangerous modules."""
    def _safe_import(name, *args, **kwargs):
        base = name.split(".")[0]
        if name in BLOCKED_MODULES or base in BLOCKED_MODULES:
            raise ImportError(
                f"Import of '{name}' is blocked in the ct sandbox for safety. "
                f"Use pre-built tools for operations requiring system access."
            )
        return real_import(name, *args, **kwargs)
    return _safe_import


def _is_within(path: Path, root: Path) -> bool:
    """Return True if path is located under root."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _session_workspace_roots() -> list[Path]:
    """Session workspace + project mount (symlink target) when set."""
    import os

    raw = str(os.environ.get("SANDWALK_SESSION_WORKSPACE") or "").strip()
    if not raw:
        return []
    try:
        root = Path(raw).expanduser().resolve()
    except OSError:
        return []
    if not root.is_dir():
        return []
    roots = [root]
    try:
        from agent_server.project_folder import project_mount_target

        target = project_mount_target(root)
        if target is not None:
            roots.append(target)
    except Exception:  # noqa: BLE001
        pass
    return roots


def make_safe_open(output_dir: Path, extra_read_dirs: list[Path] = None):
    """Restrict sandbox file I/O to safe paths."""
    real_open = open
    output_root = output_dir.resolve()
    cwd_root = Path.cwd().resolve()
    extra_roots = [d.resolve() for d in (extra_read_dirs or [])]

    def _safe_open(file, mode="r", *args, **kwargs):
        if isinstance(file, int):
            # Allow file descriptors (stdout/stderr) used by internal libs.
            return real_open(file, mode, *args, **kwargs)

        path = Path(file).expanduser()
        resolved = path.resolve() if path.is_absolute() else (cwd_root / path).resolve()

        downloads_root = (CONFIG_DIR / "downloads").resolve()
        tmp_root = Path("/tmp").resolve()
        # Read env live: the session workspace may be set after the sandbox is
        # constructed (agent-server sets it per turn).
        workspace_roots = _session_workspace_roots()
        in_workspace = any(_is_within(resolved, root) for root in workspace_roots)
        can_read = (
            _is_within(resolved, cwd_root)
            or _is_within(resolved, output_root)
            or _is_within(resolved, downloads_root)
            or _is_within(resolved, tmp_root)
            or in_workspace
            or any(_is_within(resolved, d) for d in extra_roots)
        )
        if not can_read:
            raise PermissionError(
                f"Sandbox file reads are restricted to {cwd_root}, {output_root}, and {downloads_root}"
            )

        writes = any(flag in mode for flag in ("w", "a", "x", "+"))
        tmp_root = Path("/tmp").resolve()
        if writes and not (
            _is_within(resolved, output_root)
            or _is_within(resolved, tmp_root)
            or in_workspace
        ):
            raise PermissionError(
                f"Sandbox file writes are restricted to {output_root}, /tmp, "
                "and the session workspace"
            )

        if writes:
            resolved.parent.mkdir(parents=True, exist_ok=True)

        return real_open(resolved, mode, *args, **kwargs)

    return _safe_open


ALLOWED_SUBPROCESS_COMMANDS = frozenset({
    "bwa", "samtools", "busco", "minimap2", "bowtie2",
    "muscle", "mafft", "clustalw", "phykit",
})


def make_safe_subprocess(allowed_commands: frozenset[str] = ALLOWED_SUBPROCESS_COMMANDS):
    """Create a restricted subprocess.run that only allows whitelisted bioinformatics commands."""
    import subprocess as _subprocess

    def safe_subprocess_run(cmd, **kwargs):
        """Run a whitelisted command. Only bwa, samtools, busco, minimap2, bowtie2 are allowed."""
        if not cmd:
            raise PermissionError("Empty command")
        binary = str(cmd[0]).split("/")[-1]  # handle full paths
        if binary not in allowed_commands:
            raise PermissionError(
                f"Command '{binary}' not in allowed list: {sorted(allowed_commands)}. "
                f"Only bioinformatics CLI tools are permitted."
            )
        kwargs.setdefault("timeout", 600)
        kwargs.setdefault("capture_output", True)
        # Use text mode with error handling for non-UTF8 output
        if "text" not in kwargs and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
            kwargs["errors"] = "replace"
        return _subprocess.run(cmd, **kwargs)

    return safe_subprocess_run
