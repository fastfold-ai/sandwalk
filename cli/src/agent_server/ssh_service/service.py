"""SSH Manager, Remote Execution, Tunneling, and VS Code-style Auto-Bootstrap Service."""

from __future__ import annotations

import logging
import os
import shlex
import socket
import stat
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_server.models.automations import (
    CreateSshHostRequest,
    SshBootstrapStep,
    SshConfigFileResponse,
    SshConnectRequest,
    SshConnectResponse,
    SshExecResponse,
    SshHost,
    SshProbeResult,
    SshSlurmQueueEntry,
    SshSlurmStatusResponse,
    SshSyncResponse,
    UpdateSshHostRequest,
)
from agent_server.ssh_service.config_discovery import (
    discover_ssh_config_hosts,
    parse_ssh_target_string,
)
from agent_server.store import AgentStore

logger = logging.getLogger("agent_server.ssh")

# Active local SSH tunnel processes keyed by host.id
_ACTIVE_TUNNELS: dict[str, tuple[int, subprocess.Popen[Any]]] = {}


def _find_free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _is_local_port_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.6):
            return True
    except OSError:
        return False


class SshService:
    """Manages SSH host discovery/CRUD, remote commands, Slurm status, auto-install, and tunnels."""

    def __init__(self, store: AgentStore) -> None:
        self.store = store

    def list_hosts(self, *, include_ssh_config: bool = True) -> list[SshHost]:
        saved = self.store.list_saved_ssh_hosts()
        saved_keys = {
            (h.alias.lower(), h.host.lower()) for h in saved
        } | {h.alias.lower() for h in saved}

        out: list[SshHost] = []
        for h in saved:
            out.append(self._attach_live_tunnel_state(h))

        if include_ssh_config:
            for cfg_host in discover_ssh_config_hosts():
                if (
                    cfg_host.alias.lower() in saved_keys
                    or (cfg_host.alias.lower(), cfg_host.host.lower()) in saved_keys
                ):
                    continue
                out.append(self._attach_live_tunnel_state(cfg_host))
        return out

    def _attach_live_tunnel_state(self, host: SshHost) -> SshHost:
        entry = _ACTIVE_TUNNELS.get(host.id)
        if entry is not None:
            local_port, proc = entry
            if proc.poll() is None and _is_local_port_listening(local_port):
                return host.model_copy(
                    update={
                        "tunnel_local_port": local_port,
                        "tunnel_url": f"http://127.0.0.1:{local_port}",
                        "status": "tunnel_active",
                    }
                )
            _ACTIVE_TUNNELS.pop(host.id, None)
        return host

    def resolve_or_create_host(self, id_or_target: str) -> SshHost:
        cleaned = (id_or_target or "").strip()
        if not cleaned:
            raise ValueError("SSH host or target is required.")

        # 1. Check saved hosts
        saved = self.store.get_ssh_host(cleaned)
        if saved is not None:
            return self._attach_live_tunnel_state(saved)

        # 2. Check ~/.ssh/config discovered hosts
        if cleaned.startswith("ssh-config:"):
            alias_needle = cleaned.split(":", 1)[1].strip()
        else:
            alias_needle = cleaned
        for cfg in discover_ssh_config_hosts():
            if cfg.alias.lower() == alias_needle.lower() or cfg.id.lower() == cleaned.lower():
                return self.store.upsert_ssh_host(
                    alias=cfg.alias,
                    host=cfg.host,
                    user=cfg.user,
                    port=cfg.port,
                    identity_file=cfg.identity_file,
                    proxy_jump=cfg.proxy_jump,
                    remote_port=cfg.remote_port,
                )

        # 3. Parse raw target string (`user@host -p 2222` or `host`)
        parsed = parse_ssh_target_string(cleaned)
        return self.store.upsert_ssh_host(
            alias=parsed.alias,
            host=parsed.host,
            user=parsed.user,
            port=parsed.port,
            identity_file=parsed.identity_file,
            proxy_jump=parsed.proxy_jump,
        )

    def create_host(self, req: CreateSshHostRequest) -> SshHost:
        parsed = parse_ssh_target_string(req.target)
        return self.store.upsert_ssh_host(
            alias=(req.alias or "").strip() or parsed.alias,
            host=parsed.host,
            user=parsed.user,
            port=req.port or parsed.port,
            identity_file=req.identity_file or parsed.identity_file,
            proxy_jump=req.proxy_jump or parsed.proxy_jump,
            remote_port=req.remote_port or 8787,
            default_workdir=req.default_workdir,
        )

    def update_host(self, host_id: str, req: UpdateSshHostRequest) -> SshHost | None:
        current = self.store.get_ssh_host(host_id)
        if current is None:
            return None
        updates: dict[str, Any] = {}
        for field in (
            "alias",
            "host",
            "user",
            "port",
            "identity_file",
            "proxy_jump",
            "remote_port",
            "default_workdir",
        ):
            val = getattr(req, field, None)
            if val is not None:
                updates[field] = val
        return self.store.update_ssh_host_status(current.id, **updates)

    def delete_host(self, host_id: str) -> bool:
        self.close_tunnel(host_id)
        return self.store.delete_ssh_host(host_id)

    # --- Low-Level SSH Command & Rsync Builders ---

    def _build_ssh_base_args(
        self,
        host: SshHost,
        *,
        connect_timeout: int = 10,
        batch_mode: bool = True,
    ) -> list[str]:
        args = ["ssh"]
        if batch_mode:
            args.extend(["-o", "BatchMode=yes"])
        else:
            args.extend(
                [
                    "-o",
                    "BatchMode=no",
                    "-o",
                    "PreferredAuthentications=keyboard-interactive,password,publickey",
                    "-o",
                    "NumberOfPasswordPrompts=1",
                ]
            )
        args.extend(
            [
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-o",
                f"ConnectTimeout={connect_timeout}",
                "-p",
                str(host.port or 22),
            ]
        )
        if host.identity_file:
            args.extend(["-i", str(Path(host.identity_file).expanduser())])
        if host.proxy_jump:
            args.extend(["-J", host.proxy_jump])
        destination = f"{host.user}@{host.host}" if host.user else host.host
        args.append(destination)
        return args

    def _ensure_local_public_key(self) -> str | None:
        ssh_dir = (Path.home() / ".ssh").expanduser()
        ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        for name in ("id_ed25519.pub", "id_rsa.pub", "id_ecdsa.pub"):
            pub_path = ssh_dir / name
            if pub_path.exists():
                text = pub_path.read_text(encoding="utf-8", errors="replace").strip()
                if text:
                    return text
        key_path = ssh_dir / "id_ed25519"
        if not key_path.exists():
            subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
        pub_path = ssh_dir / "id_ed25519.pub"
        if pub_path.exists():
            return pub_path.read_text(encoding="utf-8", errors="replace").strip() or None
        return None

    def _install_ssh_key_with_password(self, host: SshHost, password: str) -> tuple[bool, str]:
        """Use SSH_ASKPASS_REQUIRE=force to authenticate with password and install local public key."""
        pub_key = self._ensure_local_public_key()
        remote_cmd = "echo AUTH_OK=1"
        if pub_key:
            q_pub = shlex.quote(pub_key)
            remote_cmd = (
                "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
                "touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
                f"(grep -qxF {q_pub} ~/.ssh/authorized_keys 2>/dev/null || echo {q_pub} >> ~/.ssh/authorized_keys) && "
                "echo AUTH_OK=1"
            )
        with tempfile.TemporaryDirectory(prefix="sw-askpass-") as tmpdir:
            askpass_script = Path(tmpdir) / "askpass.sh"
            askpass_script.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$SANDWALK_SSH_PASS"\n',
                encoding="utf-8",
            )
            askpass_script.chmod(stat.S_IRWXU)
            env = dict(os.environ)
            env["SSH_ASKPASS"] = str(askpass_script)
            env["SSH_ASKPASS_REQUIRE"] = "force"
            env["DISPLAY"] = env.get("DISPLAY") or "sandwalk:0"
            env["SANDWALK_SSH_PASS"] = password
            ssh_args = [
                *self._build_ssh_base_args(host, connect_timeout=15, batch_mode=False),
                remote_cmd,
            ]
            try:
                proc = subprocess.run(
                    ssh_args,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=20.0,
                )
                out = (proc.stdout or "") + "\n" + (proc.stderr or "")
                if proc.returncode == 0 and "AUTH_OK=1" in out:
                    return True, "Authenticated and installed SSH public key"
                return False, (proc.stderr or proc.stdout or "Password authentication failed").strip()[:300]
            except Exception as exc:
                return False, str(exc)[:300]

    def get_ssh_config_file(self, config_path: Path | None = None) -> SshConfigFileResponse:
        path = (config_path or (Path.home() / ".ssh" / "config")).expanduser()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("# Sandwalk SSH Config\n", encoding="utf-8")
            path.chmod(0o600)
        return SshConfigFileResponse(
            path=str(path),
            content=path.read_text(encoding="utf-8", errors="replace"),
        )

    def update_ssh_config_file(
        self, content: str, config_path: Path | None = None
    ) -> SshConfigFileResponse:
        path = (config_path or (Path.home() / ".ssh" / "config")).expanduser()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
        return SshConfigFileResponse(path=str(path), content=content)

    def upsert_ssh_config_block(
        self, host: SshHost, config_path: Path | None = None
    ) -> None:
        """Write or update a `Host <alias>` block in ~/.ssh/config."""
        cfg = self.get_ssh_config_file(config_path)
        alias = (host.alias or host.host).strip()
        if not alias:
            return
        lines = [
            f"Host {alias}",
            f"  HostName {host.host}",
        ]
        if host.user:
            lines.append(f"  User {host.user}")
        if host.port and host.port != 22:
            lines.append(f"  Port {host.port}")
        if host.identity_file:
            lines.append(f"  IdentityFile {host.identity_file}")
        if host.proxy_jump:
            lines.append(f"  ProxyJump {host.proxy_jump}")
        block_str = "\n".join(lines) + "\n"
        if f"Host {alias}\n" in cfg.content or f"Host {alias} " in cfg.content:
            return
        sep = "" if cfg.content.endswith("\n") or not cfg.content else "\n"
        self.update_ssh_config_file(
            cfg.content + sep + "\n" + block_str, config_path=config_path
        )

    def exec_command(
        self,
        host_id_or_target: str,
        command: str,
        *,
        workdir: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> SshExecResponse:
        host = self.resolve_or_create_host(host_id_or_target)
        effective_workdir = workdir or host.default_workdir
        remote_cmd = command.strip()
        if effective_workdir:
            remote_cmd = f"cd {shlex.quote(effective_workdir)} && {remote_cmd}"
        # Ensure ~/.local/bin and ~/.cargo/bin are on PATH for non-login SSH shells
        wrapped_cmd = (
            'export PATH="$HOME/.local/bin:$HOME/.sandwalk/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"; '
            + remote_cmd
        )
        ssh_args = [*self._build_ssh_base_args(host), wrapped_cmd]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                ssh_args,
                capture_output=True,
                text=True,
                timeout=max(5.0, timeout_seconds),
            )
            dur = round(time.monotonic() - t0, 3)
            return SshExecResponse(
                host_id=host.id,
                command=command,
                workdir=effective_workdir,
                exit_code=proc.returncode,
                stdout=proc.stdout or "",
                stderr=proc.stderr or "",
                duration_seconds=dur,
            )
        except subprocess.TimeoutExpired as exc:
            dur = round(time.monotonic() - t0, 3)
            return SshExecResponse(
                host_id=host.id,
                command=command,
                workdir=effective_workdir,
                exit_code=124,
                stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
                stderr=f"SSH command timed out after {timeout_seconds}s.",
                duration_seconds=dur,
            )
        except Exception as exc:
            dur = round(time.monotonic() - t0, 3)
            return SshExecResponse(
                host_id=host.id,
                command=command,
                workdir=effective_workdir,
                exit_code=255,
                stdout="",
                stderr=str(exc),
                duration_seconds=dur,
            )

    def sync_files(
        self,
        host_id_or_target: str,
        *,
        local_path: str,
        remote_path: str,
        direction: str = "push",
        delete: bool = False,
        timeout_seconds: float = 180.0,
    ) -> SshSyncResponse:
        host = self.resolve_or_create_host(host_id_or_target)
        ssh_transport = f"ssh -p {host.port or 22} -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
        if host.identity_file:
            ssh_transport += f" -i {shlex.quote(str(Path(host.identity_file).expanduser()))}"
        if host.proxy_jump:
            ssh_transport += f" -J {shlex.quote(host.proxy_jump)}"

        dest_prefix = f"{host.user}@{host.host}" if host.user else host.host
        local_expanded = str(Path(local_path).expanduser())
        rsync_cmd = ["rsync", "-az", "-e", ssh_transport]
        if delete:
            rsync_cmd.append("--delete")
        if direction == "pull":
            rsync_cmd.extend([f"{dest_prefix}:{remote_path}", local_expanded])
        else:
            rsync_cmd.extend([local_expanded, f"{dest_prefix}:{remote_path}"])

        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                rsync_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            dur = round(time.monotonic() - t0, 3)
            summary = (proc.stdout or proc.stderr or "Sync completed.").strip()[:500]
            return SshSyncResponse(
                host_id=host.id,
                direction="pull" if direction == "pull" else "push",
                local_path=local_expanded,
                remote_path=remote_path,
                exit_code=proc.returncode,
                summary=summary or "Sync completed.",
                duration_seconds=dur,
            )
        except Exception as exc:
            dur = round(time.monotonic() - t0, 3)
            return SshSyncResponse(
                host_id=host.id,
                direction="pull" if direction == "pull" else "push",
                local_path=local_expanded,
                remote_path=remote_path,
                exit_code=1,
                summary=str(exc),
                duration_seconds=dur,
            )

    # --- Host Probe & Slurm Status ---

    def probe_host(self, host_id_or_target: str) -> SshProbeResult:
        host = self.resolve_or_create_host(host_id_or_target)
        probe_script = (
            'echo "HOSTNAME=$(hostname)"; '
            'echo "UNAME=$(uname -s) $(uname -m)"; '
            'echo "PWD=$HOME"; '
            'echo "GPU=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -n 2 | tr \'\\n\' \',\' || true)"; '
            'echo "SLURM=$(command -v squeue >/dev/null 2>&1 && echo 1 || echo 0)"; '
            'echo "SW_BIN=$(command -v sandwalk 2>/dev/null || (test -x "$HOME/.local/bin/sandwalk" && echo "$HOME/.local/bin/sandwalk") || true)"; '
            'echo "SW_VER=$(sandwalk --version 2>/dev/null || "$HOME/.local/bin/sandwalk" --version 2>/dev/null || true)"; '
            f'echo "DAEMON=$(curl -fsS --max-time 2 http://127.0.0.1:{host.remote_port}/v1/health >/dev/null 2>&1 && echo 1 || echo 0)"'
        )
        res = self.exec_command(host.id, probe_script, timeout_seconds=15.0)
        if res.exit_code != 0:
            err_msg = (res.stderr or res.stdout or "SSH probe failed").strip()[:300]
            low_err = err_msg.lower()
            needs_auth = any(
                token in low_err
                for token in (
                    "permission denied",
                    "publickey",
                    "password",
                    "authentication failed",
                )
            )
            self.store.update_ssh_host_status(
                host.id,
                status="offline",
                last_error=err_msg,
            )
            return SshProbeResult(
                host_id=host.id,
                reachable=False,
                auth_required=needs_auth,
                detail=err_msg or "Unreachable",
            )

        kv: dict[str, str] = {}
        for line in res.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                kv[k.strip()] = v.strip()

        uname_parts = kv.get("UNAME", "").split()
        platform_str = uname_parts[0] if uname_parts else None
        arch_str = uname_parts[1] if len(uname_parts) > 1 else None
        gpu_str = kv.get("GPU", "").strip(", ") or None
        slurm_ok = kv.get("SLURM") == "1"
        sw_installed = bool(kv.get("SW_BIN"))
        sw_ver = kv.get("SW_VER") or None
        daemon_ok = kv.get("DAEMON") == "1"
        hostname = kv.get("HOSTNAME") or host.host
        default_wd = host.default_workdir or kv.get("PWD") or None

        now = datetime.now(UTC)
        self.store.update_ssh_host_status(
            host.id,
            status="online",
            hostname=hostname,
            platform=platform_str,
            arch=arch_str,
            gpu_summary=gpu_str,
            slurm_available=slurm_ok,
            sandwalk_installed=sw_installed,
            sandwalk_version=sw_ver,
            daemon_running=daemon_ok,
            default_workdir=default_wd,
            last_connected_at=now,
            last_error=None,
        )
        return SshProbeResult(
            host_id=host.id,
            reachable=True,
            hostname=hostname,
            platform=platform_str,
            arch=arch_str,
            gpu_summary=gpu_str,
            slurm_available=slurm_ok,
            sandwalk_installed=sw_installed,
            sandwalk_version=sw_ver,
            daemon_running=daemon_ok,
            default_workdir=default_wd,
            detail="Connected via SSH",
        )

    def get_slurm_status(self, host_id_or_target: str) -> SshSlurmStatusResponse:
        host = self.resolve_or_create_host(host_id_or_target)
        cmd = (
            "if command -v squeue >/dev/null 2>&1; then "
            "echo 'SLURM_AVAILABLE=1'; "
            "squeue -u $USER -h -o '%i|%P|%j|%u|%T|%M|%D|%R'; "
            "else echo 'SLURM_AVAILABLE=0'; fi"
        )
        res = self.exec_command(host.id, cmd, timeout_seconds=20.0)
        lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
        if not lines or lines[0] != "SLURM_AVAILABLE=1":
            return SshSlurmStatusResponse(
                host_id=host.id,
                slurm_available=False,
                raw_output=res.stdout or res.stderr,
            )
        jobs: list[SshSlurmQueueEntry] = []
        for row in lines[1:]:
            parts = row.split("|")
            if len(parts) >= 8:
                jobs.append(
                    SshSlurmQueueEntry(
                        job_id=parts[0],
                        partition=parts[1],
                        name=parts[2],
                        user=parts[3],
                        state=parts[4],
                        time_used=parts[5],
                        nodes=parts[6],
                        reason_or_nodelist=parts[7],
                    )
                )
        return SshSlurmStatusResponse(
            host_id=host.id,
            slurm_available=True,
            jobs=jobs,
            raw_output=res.stdout,
        )

    # --- VS Code-Style Auto-Install + 3-Layer Persistent Daemon + SSH Tunnel ---

    def connect_and_bootstrap(self, req: SshConnectRequest) -> SshConnectResponse:
        """Probe SSH host, handle password auth if provided, auto-install Sandwalk if missing, start persistent daemon, and open local SSH tunnel."""
        host = self.resolve_or_create_host(req.host_id_or_target)
        updates: dict[str, Any] = {}
        if req.alias and req.alias.strip():
            updates["alias"] = req.alias.strip()
        if req.remote_port:
            updates["remote_port"] = req.remote_port
        if req.default_workdir:
            updates["default_workdir"] = req.default_workdir
        if updates:
            host = self.store.update_ssh_host_status(host.id, **updates) or host
        if req.save_to_ssh_config:
            self.upsert_ssh_config_block(host)

        steps: list[SshBootstrapStep] = []
        key_installed = False

        # If caller supplied a password, install our local SSH key first so BatchMode works
        if req.password:
            ok_key, key_detail = self._install_ssh_key_with_password(host, req.password)
            key_installed = ok_key
            steps.append(
                SshBootstrapStep(
                    step="auth",
                    status="completed" if ok_key else "failed",
                    detail=key_detail,
                )
            )
            if not ok_key:
                fresh = self.store.get_ssh_host(host.id) or host
                return SshConnectResponse(
                    host=fresh,
                    steps=steps,
                    auth_required=True,
                    key_installed=False,
                )

        # Step 1: Probe SSH connectivity & remote environment
        probe = self.probe_host(host.id)
        if not probe.reachable:
            steps.append(
                SshBootstrapStep(
                    step="probe",
                    status="failed",
                    detail=probe.detail or "Could not reach SSH host.",
                )
            )
            fresh = self.store.get_ssh_host(host.id) or host
            return SshConnectResponse(
                host=fresh,
                steps=steps,
                auth_required=probe.auth_required,
                key_installed=key_installed,
            )

        steps.append(
            SshBootstrapStep(
                step="probe",
                status="completed",
                detail=f"Connected to {probe.hostname} ({probe.platform or 'Linux'} {probe.arch or ''})",
            )
        )

        # Step 2: Auto-install Sandwalk in user space (`~/.local/bin/sandwalk`) if missing
        sw_installed = probe.sandwalk_installed
        if not sw_installed and req.auto_install:
            install_cmd = (
                "curl -fsSL https://sandwalk.sh/install.sh | bash -s -- --no-setup "
                "|| (command -v uv >/dev/null 2>&1 && uv tool install sandwalk) "
                "|| (python3 -m pip install --user -U sandwalk)"
            )
            inst_res = self.exec_command(host.id, install_cmd, timeout_seconds=240.0)
            if inst_res.exit_code == 0:
                sw_installed = True
                ver_res = self.exec_command(
                    host.id,
                    'sandwalk --version 2>/dev/null || "$HOME/.local/bin/sandwalk" --version 2>/dev/null || true',
                    timeout_seconds=10.0,
                )
                ver_str = (ver_res.stdout or "").strip() or "installed"
                self.store.update_ssh_host_status(
                    host.id,
                    sandwalk_installed=True,
                    sandwalk_version=ver_str,
                )
                steps.append(
                    SshBootstrapStep(
                        step="install",
                        status="completed",
                        detail=f"Installed Sandwalk CLI in ~/.local/bin/sandwalk ({ver_str})",
                    )
                )
            else:
                steps.append(
                    SshBootstrapStep(
                        step="install",
                        status="failed",
                        detail=(inst_res.stderr or inst_res.stdout or "Install failed")[:300],
                    )
                )
        else:
            steps.append(
                SshBootstrapStep(
                    step="install",
                    status="completed",
                    detail=f"Sandwalk already installed ({probe.sandwalk_version or 'ready'})",
                )
            )

        # Step 3: Start persistent remote daemon (3-layer survival after SSH disconnect)
        persistence_mode = "existing"
        watchdog_installed = False
        if req.start_daemon and sw_installed:
            rport = host.remote_port or 8787
            daemon_script = f"""
mkdir -p "$HOME/.sandwalk/logs"
SW_BIN="$(command -v sandwalk 2>/dev/null || echo "$HOME/.local/bin/sandwalk")"
if curl -fsS --max-time 2 http://127.0.0.1:{rport}/v1/health >/dev/null 2>&1; then
  echo "PERSISTENCE=running"
elif command -v systemctl >/dev/null 2>&1 && systemctl --user status >/dev/null 2>&1; then
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/sandwalk.service" <<UNIT
[Unit]
Description=Sandwalk Agent & Automation Server
After=network.target

[Service]
Type=simple
ExecStart=$SW_BIN serve --host 127.0.0.1 --port {rport}
Restart=always
RestartSec=3
Environment=PATH=%h/.local/bin:%h/.sandwalk/bin:/usr/local/bin:/usr/bin:/bin
Environment=OPENBLAS_CORETYPE=ARMV8

[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload >/dev/null 2>&1 || true
  systemctl --user reset-failed sandwalk.service >/dev/null 2>&1 || true
  systemctl --user enable sandwalk.service >/dev/null 2>&1 || true
  systemctl --user restart sandwalk.service >/dev/null 2>&1 || true
  loginctl enable-linger "$USER" >/dev/null 2>&1 || true
  echo "PERSISTENCE=systemd-user"
else
  OPENBLAS_CORETYPE=ARMV8 setsid nohup "$SW_BIN" serve --host 127.0.0.1 --port {rport} > "$HOME/.sandwalk/logs/remote-serve.log" 2>&1 < /dev/null &
  echo $! > "$HOME/.sandwalk/remote-serve.pid"
  echo "PERSISTENCE=setsid-nohup"
fi
"""
            if req.enable_watchdog:
                daemon_script += f"""
if command -v crontab >/dev/null 2>&1; then
  WATCHDOG_LINE="* * * * * export PATH=\\$HOME/.local/bin:\\$HOME/.sandwalk/bin:/usr/local/bin:/usr/bin:/bin OPENBLAS_CORETYPE=ARMV8; curl -fsS --max-time 2 http://127.0.0.1:{rport}/v1/health >/dev/null 2>&1 || (setsid nohup sandwalk serve --host 127.0.0.1 --port {rport} >> \\$HOME/.sandwalk/logs/remote-serve.log 2>&1 < /dev/null &)"
  (crontab -l 2>/dev/null | grep -v "sandwalk serve --host 127.0.0.1 --port {rport}" || true; echo "$WATCHDOG_LINE") | crontab - 2>/dev/null && echo "WATCHDOG=1" || true
fi
"""
            daemon_script += f"""
for i in 1 2 3 4 5 6 7 8; do
  if curl -fsS --max-time 2 http://127.0.0.1:{rport}/v1/health >/dev/null 2>&1; then
    echo "HEALTH_OK=1"
    break
  fi
  sleep 1
done
python3 - <<'PY' 2>/dev/null || true
import json, os, pathlib
for p in [
    pathlib.Path.home() / ".config/sandwalk/settings.json",
    pathlib.Path.home() / "Library/Application Support/Sandwalk/settings.json",
]:
    if p.exists():
        data = json.loads(p.read_text())
        key = (data.get("auth") or {{}}).get("api_key") or ""
        if key:
            print("REMOTE_KEY=" + key)
            break
PY
"""
            d_res = self.exec_command(host.id, daemon_script, timeout_seconds=35.0)
            remote_api_key: str | None = None
            health_ok = False
            for ln in d_res.stdout.splitlines():
                if ln.startswith("PERSISTENCE="):
                    persistence_mode = ln.split("=", 1)[1].strip()
                elif ln.startswith("WATCHDOG=1"):
                    watchdog_installed = True
                elif ln.startswith("HEALTH_OK=1"):
                    health_ok = True
                elif ln.startswith("REMOTE_KEY="):
                    remote_api_key = ln.split("=", 1)[1].strip() or None

            steps.append(
                SshBootstrapStep(
                    step="daemon",
                    status="completed" if health_ok else "failed",
                    detail=(
                        f"Remote server active on :{rport} ({persistence_mode}"
                        + (", crontab watchdog enabled)" if watchdog_installed else ")")
                        if health_ok
                        else "Remote daemon did not respond on /v1/health"
                    ),
                )
            )
            if health_ok:
                self.store.update_ssh_host_status(host.id, daemon_running=True)
        else:
            remote_api_key = None

        # Step 4: Open local SSH port-forward tunnel (`ssh -N -L local:127.0.0.1:remote`)
        local_url: str | None = None
        if req.open_tunnel:
            try:
                local_port = self.open_tunnel(host.id)
                local_url = f"http://127.0.0.1:{local_port}"
                steps.append(
                    SshBootstrapStep(
                        step="tunnel",
                        status="completed",
                        detail=f"SSH tunnel ready at {local_url} → {host.host}:{host.remote_port}",
                    )
                )
            except Exception as exc:
                steps.append(
                    SshBootstrapStep(
                        step="tunnel",
                        status="failed",
                        detail=str(exc),
                    )
                )

        updated_host = self._attach_live_tunnel_state(
            self.store.get_ssh_host(host.id) or host
        )
        return SshConnectResponse(
            host=updated_host,
            steps=steps,
            auth_required=False,
            key_installed=key_installed,
            local_url=local_url,
            remote_api_key=remote_api_key,
            hostname=updated_host.hostname or updated_host.host,
            platform=updated_host.platform,
            daemon_persistence=persistence_mode,
            watchdog_installed=watchdog_installed,
        )

    def open_tunnel(self, host_id_or_target: str) -> int:
        host = self.resolve_or_create_host(host_id_or_target)
        existing = _ACTIVE_TUNNELS.get(host.id)
        if existing is not None:
            lport, proc = existing
            if proc.poll() is None and _is_local_port_listening(lport):
                return lport
            _ACTIVE_TUNNELS.pop(host.id, None)

        local_port = _find_free_local_port()
        ssh_cmd = [
            "ssh",
            "-N",
            "-o",
            "BatchMode=yes",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ServerAliveInterval=30",
            "-o",
            "ServerAliveCountMax=3",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-p",
            str(host.port or 22),
            "-L",
            f"127.0.0.1:{local_port}:127.0.0.1:{host.remote_port or 8787}",
        ]
        if host.identity_file:
            ssh_cmd.extend(["-i", str(Path(host.identity_file).expanduser())])
        if host.proxy_jump:
            ssh_cmd.extend(["-J", host.proxy_jump])
        dest = f"{host.user}@{host.host}" if host.user else host.host
        ssh_cmd.append(dest)

        proc = subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(25):
            if proc.poll() is not None:
                err = (proc.stderr.read() if proc.stderr else "") or "SSH tunnel exited"
                raise RuntimeError(f"SSH tunnel failed: {err.strip()[:240]}")
            if _is_local_port_listening(local_port):
                _ACTIVE_TUNNELS[host.id] = (local_port, proc)
                self.store.update_ssh_host_status(
                    host.id,
                    status="tunnel_active",
                    tunnel_local_port=local_port,
                    tunnel_url=f"http://127.0.0.1:{local_port}",
                )
                return local_port
            time.sleep(0.15)

        proc.terminate()
        raise RuntimeError("Timed out waiting for local SSH tunnel port to bind.")

    def close_tunnel(self, host_id: str) -> bool:
        entry = _ACTIVE_TUNNELS.pop(host_id, None)
        if entry is not None:
            _, proc = entry
            try:
                proc.terminate()
            except Exception:
                pass
        self.store.update_ssh_host_status(
            host_id,
            status="online",
            tunnel_local_port=None,
            tunnel_url=None,
        )
        return entry is not None
