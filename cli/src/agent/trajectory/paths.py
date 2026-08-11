"""Session file path resolution and listing for Trajectory."""

import json
from pathlib import Path

from agent.config import CONFIG_DIR


class PathsMixin:
    """Adds session directory/path resolution and listing to Trajectory."""

    @staticmethod
    def sessions_dir() -> Path:
        """Return the directory where sessions are stored."""
        d = CONFIG_DIR / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def session_path(cls, session_id: str) -> Path:
        """Return canonical path for a saved session."""
        return cls.sessions_dir() / f"{session_id}.jsonl"

    @classmethod
    def trace_path(cls, session_id: str) -> Path:
        """Return canonical path for a saved session trace."""
        return cls.sessions_dir() / f"{session_id}.trace.jsonl"

    @classmethod
    def resolve_session_path(cls, path_or_session_id: Path | str) -> Path:
        """Resolve exact path or session id/prefix into a session JSONL path."""
        if isinstance(path_or_session_id, Path):
            return path_or_session_id
        raw = str(path_or_session_id or "").strip()
        if not raw:
            raise FileNotFoundError("No session id provided.")
        if raw.endswith(".jsonl") or "/" in raw:
            path = Path(raw)
            if path.exists():
                return path
            raise FileNotFoundError(f"Session file not found: {raw}")

        exact = cls.session_path(raw)
        if exact.exists():
            return exact

        matches = [s for s in cls.list_sessions() if str(s.get("session_id", "")).startswith(raw)]
        if len(matches) == 1:
            return Path(matches[0]["path"])
        if len(matches) > 1:
            ids = ", ".join(str(s.get("session_id", "")) for s in matches[:5])
            raise FileNotFoundError(f"Session id '{raw}' is ambiguous. Matches: {ids}")
        raise FileNotFoundError(f"Session '{raw}' not found.")

    @classmethod
    def list_sessions(cls) -> list[dict]:
        """List all saved sessions, most recent first."""
        sessions_dir = cls.sessions_dir()
        sessions = []
        for path in sessions_dir.glob("*.jsonl"):
            if path.name.endswith(".trace.jsonl"):
                continue
            try:
                with open(path) as f:
                    first_line = f.readline().strip()
                    if first_line:
                        meta = json.loads(first_line)
                        if meta.get("type") == "meta":
                            meta["path"] = str(path)
                            meta["updated_at"] = meta.get("updated_at", meta.get("created_at", 0))
                            sessions.append(meta)
            except (json.JSONDecodeError, OSError):
                continue
        # Sort by last activity descending (most recent first)
        sessions.sort(key=lambda s: s.get("updated_at", s.get("created_at", 0)), reverse=True)
        return sessions

    @classmethod
    def delete_session(cls, path_or_session_id: Path | str) -> dict:
        """Delete a saved session and its associated trace file."""
        session_path = cls.resolve_session_path(path_or_session_id)
        session_id = session_path.stem

        session_path.unlink()

        trace_path = cls.trace_path(session_id)
        trace_deleted = False
        if trace_path.exists():
            trace_path.unlink()
            trace_deleted = True

        return {
            "session_id": session_id,
            "session_deleted": True,
            "trace_deleted": trace_deleted,
        }
