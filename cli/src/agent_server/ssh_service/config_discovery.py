"""Parse ~/.ssh/config and SSH connection strings (`user@host -p 22`)."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from agent_server.models.automations import SshHost


@dataclass
class ParsedSshTarget:
    alias: str
    host: str
    user: str | None = None
    port: int = 22
    identity_file: str | None = None
    proxy_jump: str | None = None


def parse_ssh_target_string(raw: str) -> ParsedSshTarget:
    """Parse `ssh -p 2222 -i ~/.ssh/id_ed25519 user@cluster.edu` or `user@host:2222`."""
    cleaned = (raw or "").strip()
    if not cleaned:
        raise ValueError("SSH target cannot be empty.")

    try:
        tokens = shlex.split(cleaned)
    except ValueError:
        tokens = cleaned.split()

    if tokens and tokens[0] == "ssh":
        tokens = tokens[1:]

    port = 22
    identity_file: str | None = None
    proxy_jump: str | None = None
    user_opt: str | None = None
    positional: list[str] = []

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "-p" and i + 1 < len(tokens):
            port = int(tokens[i + 1])
            i += 2
            continue
        if tok == "-i" and i + 1 < len(tokens):
            identity_file = tokens[i + 1]
            i += 2
            continue
        if tok == "-J" and i + 1 < len(tokens):
            proxy_jump = tokens[i + 1]
            i += 2
            continue
        if tok == "-l" and i + 1 < len(tokens):
            user_opt = tokens[i + 1]
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        positional.append(tok)
        i += 1

    target = positional[0] if positional else cleaned
    if target.startswith("ssh://"):
        target = target[len("ssh://") :]

    user: str | None = user_opt
    if "@" in target:
        user_part, target = target.split("@", 1)
        user = user_part.strip() or user

    if ":" in target and not target.startswith("["):
        host_part, port_part = target.rsplit(":", 1)
        if port_part.isdigit():
            target = host_part
            port = int(port_part)

    host = target.strip().rstrip("/")
    if not host:
        raise ValueError(f"Invalid SSH host in {raw!r}")
    alias = host.split(".")[0] if "." in host and not re.match(r"^\d+\.\d+\.\d+\.\d+$", host) else host
    return ParsedSshTarget(
        alias=alias,
        host=host,
        user=user,
        port=port,
        identity_file=identity_file,
        proxy_jump=proxy_jump,
    )


def discover_ssh_config_hosts(config_path: Path | None = None) -> list[SshHost]:
    """Parse ~/.ssh/config for non-wildcard Host blocks."""
    path = (config_path or (Path.home() / ".ssh" / "config")).expanduser()
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []

    blocks: list[tuple[list[str], dict[str, str]]] = []
    current_aliases: list[str] = []
    current_opts: dict[str, str] = {}

    for raw_line in lines:
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        key, val = parts[0].lower(), parts[1].strip().strip('"')
        if key == "host":
            if current_aliases:
                blocks.append((current_aliases, current_opts))
            current_aliases = [
                a for a in val.split() if "*" not in a and "?" not in a and not a.startswith("!")
            ]
            current_opts = {}
        elif current_aliases:
            current_opts[key] = val

    if current_aliases:
        blocks.append((current_aliases, current_opts))

    now = datetime.now(UTC)
    discovered: list[SshHost] = []
    seen_aliases: set[str] = set()
    for aliases, opts in blocks:
        for alias in aliases:
            low = alias.lower()
            if low in seen_aliases or low in {"github.com", "gitlab.com", "bitbucket.org"}:
                continue
            seen_aliases.add(low)
            hostname = opts.get("hostname", alias)
            user = opts.get("user")
            try:
                port = int(opts.get("port", "22"))
            except ValueError:
                port = 22
            identity = opts.get("identityfile")
            proxy_jump = opts.get("proxyjump")
            discovered.append(
                SshHost(
                    id=f"ssh-config:{alias}",
                    alias=alias,
                    host=hostname,
                    user=user,
                    port=port,
                    identity_file=identity,
                    proxy_jump=proxy_jump,
                    remote_port=8787,
                    source="ssh_config",
                    status="unknown",
                    created_at=now,
                    updated_at=now,
                )
            )
    return discovered
