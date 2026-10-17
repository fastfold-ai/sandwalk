"""`entry()` — process entry point invoked by the `sandwalk` / `fastfold` console scripts."""

import os
import sys
from pathlib import Path

from cli.app import app

SUBCOMMANDS = {
    "config",
    "data",
    "tool",
    "skills",
    "skill",
    "add",
    "trace",
    "knowledge",
    "keys",
    "auth",
    "mcp",
    "specialists",
    "sandbox",
    "serve",
    "sync",
    "doctor",
    "setup",
    "release-check",
    "upgrade",
    "desktop",
    "report",
    "case-study",
    "bench",
    "eval",
    "agent",
    "fork",
    "run",  # legacy explicit runner command
    "--help",
    "-h",
    "--install-completion",
    "--show-completion",
}


def entry():
    """Package entry point."""
    # Support --offline flag: set env var before importing the app
    if "--offline" in sys.argv:
        os.environ["SANDWALK_FORCE_OFFLINE"] = "1"
        # Remove --offline from args so the app doesn't see it as a subcommand
        sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a != "--offline"]
    # Dev ergonomics: when invoked from the repo root (or a subdir), prefer the
    # live source tree so `uv run sandwalk ...` reflects local edits immediately.
    current_pkg_init = Path(__file__).resolve().parent / "__init__.py"
    candidate_roots = [Path.cwd(), *Path.cwd().parents]
    for root in candidate_roots:
        local_pkg_init = root / "src" / "cli" / "__init__.py"
        if not local_pkg_init.exists():
            continue
        resolved_local = local_pkg_init.resolve()
        if resolved_local == current_pkg_init.resolve():
            break
        local_src = str((root / "src").resolve())
        code = f"import sys; sys.path.insert(0, {local_src!r}); from cli import entry as _e; _e()"
        os.execv(sys.executable, [sys.executable, "-c", code, *sys.argv[1:]])

    argv = list(sys.argv[1:])

    # Support `sandwalk help` and `sandwalk help <subcommand>` as aliases.
    if argv and argv[0] == "help":
        argv = ["--help"] if len(argv) == 1 else [*argv[1:], "--help"]

    # Route plain invocations to hidden `run` command so:
    #   fastfold                       -> interactive mode
    #   sandwalk "question"            -> single-query mode
    #   sandwalk --smiles ... "q"      -> single-query with context
    # while preserving explicit subcommands like `sandwalk config ...`.
    # Backward-compat: allow old `sandwalk run <subcommand> ...` invocations by
    # unwrapping the legacy `run` prefix when the remainder is a real subcommand.
    if len(argv) >= 2 and argv[0] == "run" and argv[1] in SUBCOMMANDS:
        argv = argv[1:]

    if not argv or argv[0] not in SUBCOMMANDS:
        argv = ["run", *argv]

    app(args=argv, prog_name="sandwalk")
