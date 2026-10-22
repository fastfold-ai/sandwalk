---
name: ssh
description: Connect to remote SSH servers, execute remote commands on Linux and macOS machines, sync workspace files via rsync, manage ~/.ssh/config hosts, and auto-bootstrap persistent remote Sandwalk daemons and tunnels.
author: sandwalk
category: Built-in
version: 1.0.0
---

# Sandwalk SSH & Remote Server Manager (`/ssh`)

Sandwalk agents can manage and execute workloads on any remote SSH server, Linux VM, cloud instance, or workstation using built-in `ssh.*` tools or standard terminal `ssh` and `rsync` commands.

## 1. Built-In SSH Tools

1. **`ssh.hosts(action="list" | "add" | "probe" | "remove", target="user@host -p 22", alias="my-server", default_workdir="/home/user/workspace")`**:
   - Automatically discovers hosts from `~/.ssh/config` and merges them with saved Sandwalk SSH hosts.
   - `probe` checks connectivity, OS/architecture, available hardware, and whether `sandwalk` is installed and running remotely.
2. **`ssh.exec(host="my-server", command="...", workdir="/home/user/workspace")`**:
   - Runs non-interactive commands on the remote host with `~/.local/bin` and `~/.sandwalk/bin` on `PATH`.
3. **`ssh.sync(host="my-server", local_path="./project/", remote_path="/home/user/workspace/project/", direction="push" | "pull")`**:
   - Uses `rsync -az` over SSH to push local files or directories to a remote workspace or pull remote outputs back locally.
4. **`ssh.bootstrap_remote(host="my-server", default_workdir="/home/user/workspace")`**:
   - Installs Sandwalk in user space (`~/.local/bin/sandwalk` — no root/sudo required), starts a persistent background `sandwalk serve` daemon (`systemd --user` or detached `setsid nohup` + `crontab` watchdog) so remote sessions and Automations keep running after you disconnect, and opens a local SSH port-forward tunnel.

## 2. Best Practices for Remote SSH Workflows

- **User-Space First**: Prefer user-space paths (`~/.local/bin`, `~/.sandwalk`, user virtualenvs or `uv` tools) so commands work cleanly even without `sudo`.
- **Sync Before & After**: Use `ssh.sync` (`direction="push"`) to mirror code or configs before running remote commands, and `direction="pull"` to retrieve generated artifacts or logs.
- **Persistent Remote Server**: Use `ssh.bootstrap_remote` when you want a full remote Sandwalk server running in the background on the target machine and tunneled to your local desktop client.
