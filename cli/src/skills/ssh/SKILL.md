---
name: ssh
description: Manage SSH servers, execute remote commands on Linux/macOS/HPC machines, inspect and submit Slurm jobs (squeue/sbatch/sacct), sync workspace files via rsync, and auto-bootstrap persistent remote Sandwalk daemons.
author: sandwalk
category: Built-in
version: 1.0.0
---

# Sandwalk SSH & HPC / Slurm Manager (`/ssh`)

Sandwalk agents can manage and execute workloads on remote SSH servers, university Linux login nodes, and GPU/Slurm clusters using built-in `ssh.*` tools or standard terminal `ssh`/`rsync` commands.

## 1. Built-In SSH Tools

1. **`ssh.hosts(action="list" | "add" | "probe" | "remove", target="user@host -p 22", alias="hpc", default_workdir="/scratch/user")`**:
   - Automatically discovers hosts from `~/.ssh/config` and merges them with saved Sandwalk SSH hosts.
   - `probe` checks connectivity, OS/arch, GPUs (`nvidia-smi`), Slurm (`squeue`), and whether `sandwalk` is installed remotely.
2. **`ssh.exec(host="hpc", command="...", workdir="/scratch/user/run-1")`**:
   - Runs non-interactive commands on the remote host with `~/.local/bin` and `~/.sandwalk/bin` on `PATH`.
3. **`ssh.sync(host="hpc", local_path="./configs/", remote_path="/scratch/user/run-1/configs/", direction="push" | "pull")`**:
   - Uses `rsync -az` over SSH to push inputs/scripts to a shared cluster workspace or pull results back locally.
4. **`ssh.slurm_status(host="hpc")`**:
   - Returns structured active Slurm jobs (`job_id`, `partition`, `name`, `state`, `time_used`, `nodes`, `reason_or_nodelist`).
5. **`ssh.bootstrap_remote(host="hpc", default_workdir="/scratch/user")`**:
   - Installs Sandwalk in user space (`~/.local/bin/sandwalk` — no root/sudo required), starts a persistent background `sandwalk serve` daemon (`systemd --user` or detached `setsid nohup` + `crontab` watchdog) so remote Automations keep running 24/7 after you close your laptop, and opens a local SSH port-forward tunnel.

## 2. Best Practices for University & Slurm Clusters

- **User-Space Only**: Never assume `sudo` on shared university or HPC machines; install into `~/.local/bin`, `~/.sandwalk`, or user conda/`uv` environments.
- **Keep Login Nodes Light**: Run heavy compute via `sbatch` or `srun` rather than directly on the SSH login node.
- **Pair with Automations**: After submitting `sbatch`, schedule a recurring watcher (`automation.manage(action="create", schedule="every 15m", ssh_host=..., command="squeue -u $USER", wake_on_change_only=True)`) or append `curl -fsS -X POST <webhook_url>` at the end of your `.slurm` script.
