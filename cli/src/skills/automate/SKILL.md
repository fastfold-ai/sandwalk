---
name: automate
description: Schedule and manage recurring agent workflows, cron jobs, one-shot follow-ups, thread snoozing, and Slurm/SSH job watchers in Sandwalk.
author: sandwalk
category: Built-in
version: 1.0.0
---

# Sandwalk Automations (`/automate` & Cron)

Sandwalk lets you schedule recurring agent tasks, one-time reminders, and zero-token shell/SSH watchers through the unified `automation.manage` tool, the **Automations** view, or `sandwalk cron` on the CLI.

## 1. Choosing the Right Execution Mode (`session_mode`)

| Mode | When to Use | How it Works |
|---|---|---|
| `continue` | In-thread follow-ups, reminders, or watching a job (`sbatch`, training, deploy) until completion | Wakes the **same session** on schedule so full conversation context is preserved. Pair with `snooze` so background ticks stay quiet until `unsnooze` or `complete`. |
| `fresh` | Daily/hourly digests, literature scouts, overnight Boltz/docking reviews, PR/test audits | Starts a **clean session** per run. Turn on `continuity=True` so the previous run's output is prepended and the agent never repeats old items. |
| `no_agent` | Lightweight `squeue`, `nvidia-smi`, or disk quota polling | Runs `command` locally or over SSH without calling an LLM. Combine with `context_from` or `wake_on_change_only=True` to wake an agent only when output changes. |

## 2. Supported Schedule Formats (`schedule`)

- **One-shot delays**: `in 30m`, `in 2h`, `in 1d`, or ISO timestamps (`2026-10-21T09:00:00`)
- **Recurring intervals**: `every 15m`, `every 2h`, `every 1d`, `hourly`
- **Natural day/time**: `daily at 9am`, `weekdays at 8:30am`, `every monday at 9am`
- **5-field cron**: `0 9 * * 1-5`, `*/15 * * * *`
- **Event / Webhook**: `webhook` (generates `POST /v1/automations/webhook/<token>` for `.slurm` scripts or CI hooks)

## 3. Tool Recipes (`automation.manage`)

- **Schedule a Slurm / HPC job watcher in the current thread**:
  ```python
  automation.manage(
      action="create",
      name="Watch Slurm GLP-1R Array",
      schedule="every 15m",
      session_mode="continue",
      ssh_host="hpc-cluster",
      remote_workdir="/scratch/$USER/glp1r-md",
      command="squeue -u $USER",
      wake_on_change_only=True,
      prompt="Check squeue and sacct. If any task failed, inspect slurm-*.err. When all tasks finish, summarize outputs and call automation.manage(action='complete').",
  )
  ```
- **Create a daily deduplicated scout with Continuity**:
  ```python
  automation.manage(
      action="create",
      name="Morning Structure & Literature Digest",
      schedule="daily at 8:30am",
      session_mode="fresh",
      continuity=True,
      specialist_id="otium-relaxed",
      skills="omnigraph,knowledge-steward",
      prompt="Summarize new structure predictions and papers not covered in your previous run, and update the Living Wiki.",
  )
  ```
