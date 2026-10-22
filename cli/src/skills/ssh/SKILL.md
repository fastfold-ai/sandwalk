---
name: ssh
description: Encrypted remote access, SSH config and key management, rsync/scp file transfer, local/remote port forwarding, jump hosts, and persistent remote Sandwalk daemon bootstrapping.
author: sandwalk
category: Built-in
version: 1.0.0
---

# SSH Remote Access (`/ssh`)

## Overview

SSH (Secure Shell) provides encrypted remote access, file transfer, and tunneling over untrusted networks. OpenSSH is the standard implementation on Linux, macOS, and Windows, configured via `~/.ssh/config` with per-host aliases, identity management, proxy jumps, and connection multiplexing.

- **When to use**: Remote server management, command execution on Linux/macOS machines, secure file transfers (`rsync`/`scp`), local/remote port forwarding, jump host (`ProxyJump`) traversal, automated deployments, and bootstrapping persistent remote Sandwalk servers.
- **When NOT to use**: High-throughput bulk WAN data transfers (use specialized transfer tools), GUI-heavy remote desktops (use VNC/RDP), or container-native orchestration where `kubectl`/`docker` contexts already exist.

## Quick Reference

| Pattern | Command / Directive | Key Points |
| --- | --- | --- |
| Basic connect | `ssh user@host` | Add `-p PORT` for non-default port |
| Identity file | `ssh -i ~/.ssh/id_ed25519 user@host` | Specify private key explicitly |
| Remote command | `ssh user@host "command"` | Add `-t` when a pseudo-TTY is required |
| SSH config alias | `Host myserver` block in `~/.ssh/config` | Simplifies repeated connections and tools |
| File sync (`rsync`) | `rsync -avzP src/ user@host:dest/` | Preferred over `scp` for delta sync and resume |
| File copy (`scp`) | `scp file user@host:path` | Quick single-file copy (uses SFTP internally) |
| Local tunnel | `ssh -N -L local_port:127.0.0.1:remote_port user@host` | Forward a remote service to `127.0.0.1:local_port` |
| Remote tunnel | `ssh -N -R remote_port:127.0.0.1:local_port user@host` | Expose a local service on the remote host |
| SOCKS proxy | `ssh -D 1080 user@host` | Dynamic application-level port forwarding |
| Jump host | `ssh -J bastion user@target` | `ProxyJump` traversal through bastion hosts |
| Key generation | `ssh-keygen -t ed25519 -C "comment"` | Recommended default for all new keys |
| FIDO2 hardware key | `ssh-keygen -t ed25519-sk` | Hardware-backed key (OpenSSH 8.2+) |
| SSH agent | `ssh-add ~/.ssh/id_ed25519` | Cache decrypted key in memory for the session |
| Multiplexing | `ControlMaster auto` + `ControlPath ~/.ssh/cm-%r@%h:%p` | Reuse existing TCP/SSH connections |
| Debug connection | `ssh -v user@host` | Up to `-vvv` for verbose auth/routing diagnostics |

## Sandwalk Built-In SSH Tools

Prefer Sandwalk's structured `ssh.*` tools when managing saved hosts, running non-interactive remote commands, syncing project files, or bootstrapping a remote Sandwalk daemon:

1. **`ssh.hosts(action="list" | "add" | "probe" | "remove", target="user@host -p 22", alias="myserver", default_workdir="/home/user/workspace")`**
   - Automatically discovers hosts from `~/.ssh/config` and merges them with saved Sandwalk SSH hosts.
   - `probe` checks reachability, OS/architecture, GPUs, and whether `sandwalk` is installed and running remotely.
2. **`ssh.exec(host="myserver", command="...", workdir="/home/user/workspace")`**
   - Executes non-interactive commands on the remote host with `~/.local/bin` and `~/.sandwalk/bin` on `PATH`.
3. **`ssh.sync(host="myserver", local_path="./src/", remote_path="/home/user/workspace/src/", direction="push" | "pull")`**
   - Runs `rsync -az` over SSH (respecting custom port, identity file, and `ProxyJump`) to push local files or pull remote outputs.
4. **`ssh.bootstrap_remote(host="myserver", default_workdir="/home/user/workspace")`**
   - Installs Sandwalk in user space (`~/.local/bin/sandwalk` — no `sudo` required), starts a persistent background `sandwalk serve` daemon (`systemd --user` or detached `setsid nohup` + `crontab` watchdog) that survives SSH disconnects, and opens a local SSH port-forward tunnel.

## Key Type Recommendations

| Algorithm | Recommendation | Notes |
| --- | --- | --- |
| **Ed25519** (`ed25519`) | Default for all new keys | Fast, compact, high security, supported on OpenSSH 6.5+ |
| **Ed25519-SK** (`ed25519-sk`) | Strongest option with hardware key | Requires FIDO2 security key, OpenSSH 8.2+ |
| **RSA 4096** (`rsa -b 4096`) | Legacy compatibility only | Use only when Ed25519 is unsupported by an older appliance |
| **ECDSA** | Avoid | Prefer Ed25519 over NIST curve implementations |

## File Transfer Decision Guide

| Scenario | Tool | Why |
| --- | --- | --- |
| Recurring syncs or project directories | `ssh.sync` / `rsync -avzP` | Delta transfer, compression, permissions, and resume |
| Quick one-off single file copy | `scp` or `ssh.sync` | Simple path syntax for single small files |
| Interactive remote file browsing | `sftp` | Interactive navigation and tab completion |

## Common Mistakes & Correct Patterns

| Mistake | Correct Pattern |
| --- | --- |
| Generating new RSA keys by default | Use `ssh-keygen -t ed25519` — faster, smaller, and modern |
| Using `scp` for large or repeated directory syncs | Use `ssh.sync` or `rsync -avzP` for delta transfers and resume |
| Connecting through bastions with nested `ssh` commands | Use `-J` / `ProxyJump` so file transfers and tunnels work end-to-end |
| Using `ForwardAgent yes` across untrusted hosts | Use `ProxyJump` instead — agent forwarding exposes your socket on intermediate hosts |
| Running interactive TUI tools without a TTY | Pass `-t` (`ssh -t user@host "htop"`) when a pseudo-terminal is required |
| Setting `ControlPath` without `%r`, `%h`, `%p` | Always include `%r@%h:%p` so multiplexed sockets never collide across hosts/users |
| Omitting `IdentitiesOnly yes` when many keys are loaded | Set `IdentitiesOnly yes` in `Host` blocks to avoid `Too many authentication failures` |
| Assuming root/`sudo` on remote servers | Install tools in user space (`~/.local/bin`, `~/.sandwalk`, `uv tool install`) |

## Security Checklist

- Use Ed25519 (`id_ed25519`) or FIDO2 (`id_ed25519_sk`) keys with `chmod 700 ~/.ssh` and `chmod 600 ~/.ssh/authorized_keys`.
- Prefer `BatchMode=yes` and `StrictHostKeyChecking=accept-new` for non-interactive automation.
- Set `IdentitiesOnly yes` in `~/.ssh/config` host blocks when using host-specific keys.
- Use `ProxyJump` (`-J`) instead of `ForwardAgent yes` for multi-hop connections.
- Keep remote daemons bound to loopback (`127.0.0.1`) and access them via SSH local port forwarding (`ssh -N -L`).
