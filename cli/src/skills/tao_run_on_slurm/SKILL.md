---
name: tao-run-on-slurm
description: Remote SLURM GPU cluster execution over SSH with sbatch/srun, Pyxis/Enroot containers, and Lustre-backed results. Use when running GPU training, evaluation, or inference jobs on an on-prem or DGX SLURM cluster.
author: NVIDIA Corporation
category: HPC & Slurm
version: 0.1.1
tags:
  - platform
  - slurm
  - nvidia
  - hpc
---

# NVIDIA `tao-run-on-slurm` — SLURM GPU Cluster Execution over SSH

Remote GPU compute skill for clusters managed by **SLURM** (`https://github.com/NVIDIA/skills/tree/HEAD/skills/tao-run-on-slurm`). Jobs are staged from your local machine to a login node over SSH, submitted with `sbatch`, and monitored via `squeue` / `sacct` / `scancel` (with optional Pyxis/Enroot `.sqsh` container execution).

## 1. Preflight + SSH

1. Confirm passwordless SSH (`ssh -o BatchMode=yes`) to the SLURM login host works (or configure the host in **Dashboard → SSH & Clusters**).
2. The launch machine only needs `ssh` (and `ssh.exec` / `ssh.slurm_status` / `ssh.sync`); `sbatch`, `srun`, `squeue`, `sacct`, and shared storage (`/scratch` or Lustre) live on the remote SLURM cluster.
3. For private `nvcr.io` images with Pyxis/Enroot, install `~/.config/enroot/.credentials` on the cluster via a mode-600 stdin pipe rather than inline environment variables.

## 2. The Four Core Verbs (`submit`, `status`, `logs`, `cancel`)

### `submit`
1. **Stage inputs and scripts to the shared cluster workspace** (`ssh.sync` or `rsync -az` to `/scratch/$USER/<job_dir>`).
2. **Acquire container images off the GPU allocation** (when using Pyxis/Enroot): convert `docker://...` to a cached `.sqsh` file on a CPU partition first so GPU walltime is never burned on image pulls.
3. **Render and lint the `sbatch` script** (`#SBATCH --job-name`, `--nodes`, `--gpus-per-node`, `--cpus-per-task`, `--time`, `--output`), then submit:
   ```bash
   SLURM_ID=$(ssh $LOGIN "sbatch --parsable <job_dir>/job.sbatch")
   ```

### `status`
Query `squeue` while `PENDING`/`RUNNING` and `sacct` for terminal states (`State%30` widened so `CANCELLED+` is not truncated):
```bash
ssh $LOGIN "squeue -j $SLURM_ID -h -o '%i|%P|%j|%u|%T|%M|%D|%R'"
ssh $LOGIN "sacct -j $SLURM_ID -X -n -o JobID,JobName%24,State%30,ExitCode,Elapsed"
```

| SLURM State | Meaning & Action |
|---|---|
| `PENDING` | Queued waiting for resources — keep polling on schedule |
| `RUNNING` / `COMPLETING` | Executing on compute node(s) |
| `COMPLETED` | Succeeded (`ExitCode 0:0`) — verify output artifacts in results dir |
| `FAILED` / `TIMEOUT` / `OUT_OF_MEMORY` | Inspect `<log_dir>/slurm-<id>.err` tail and classify infra vs. program error |
| `NODE_FAIL` / `BOOT_FAIL` | Infrastructure error — requeue (`#SBATCH --requeue`) or resubmit |
| `CANCELLED` / `PREEMPTED` | Canceled or preempted |

### `logs`
```bash
ssh $LOGIN "tail -n 200 <job_dir>/slurm-$SLURM_ID.out <job_dir>/slurm-$SLURM_ID.err"
```

### `cancel`
```bash
ssh $LOGIN "scancel $SLURM_ID"
```

## 3. Pairing with Sandwalk Automations

After submitting a SLURM job, schedule an automated watcher with `automation.manage` so Sandwalk monitors the queue every 15 minutes over SSH and wakes the thread when the job completes or fails:
```python
automation.manage(
    action="create",
    name="Watch SLURM Job",
    schedule="every 15m",
    session_mode="continue",
    ssh_host="ubuntu-slurm",
    remote_workdir="~/slurm-workspace",
    command="squeue -u $USER && sacct -X -n -o JobID,JobName%24,State%20,ExitCode,Elapsed",
    wake_on_change_only=True,
    skills="tao-run-on-slurm,ssh,automate",
    prompt="Check SLURM job status. If FAILED/TIMEOUT/OOM, read slurm-*.err and report root cause. When COMPLETED, summarize outputs and call automation.manage(action='complete').",
)
```
