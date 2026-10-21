"""Curated starter Automation templates."""

from __future__ import annotations

from agent_server.models.automations import AutomationTemplate

AUTOMATION_TEMPLATES: list[AutomationTemplate] = [
    AutomationTemplate(
        id="summarize-changes-daily",
        name="Summarize changes daily",
        category="popular",
        description=(
            "Post a daily digest summarizing notable repository or workspace changes, "
            "open questions, and risks."
        ),
        schedule_expr="daily at 9:00am",
        schedule_label="Daily at 9:00 AM",
        session_mode="fresh",
        prompt=(
            "Review recent activity, commits, and modified files in the workspace over the past 24 hours. "
            "Write a concise daily summary highlighting key progress, blockers, and next steps."
        ),
        continuity=True,
        recommended_specialist_slug="project-manager",
        skill_names=["automate", "slack_report"],
        tool_names=["ops.automation_manage"],
        badge="Scheduled · Daily Digest",
    ),
    AutomationTemplate(
        id="find-critical-bugs",
        name="Find critical bugs & regressions",
        category="code_ci",
        description=(
            "Analyze recent commits and test runs for high-severity correctness bugs, "
            "regressions, or failing checks."
        ),
        schedule_expr="weekdays at 9:00am",
        schedule_label="Weekdays at 9:00 AM",
        session_mode="fresh",
        prompt=(
            "Inspect recent git commits and run the verification suite. "
            "Report only high-severity bugs, failing tests, or regressions not already covered in the previous run."
        ),
        continuity=True,
        recommended_specialist_slug="skeptical-reviewer",
        skill_names=["automate"],
        tool_names=["ops.automation_manage"],
        badge="Scheduled · Code Review",
    ),
    AutomationTemplate(
        id="second-brain-literature-scout",
        name="Literature & Second Brain Scout",
        category="memory_wiki",
        description=(
            "Scan new papers, notes, and project updates daily and link net-new insights "
            "into your Living Wiki without repeating past reports."
        ),
        schedule_expr="daily at 8:30am",
        schedule_label="Daily at 8:30 AM",
        session_mode="fresh",
        prompt=(
            "Search for new relevant papers or technical updates and review recent session notes. "
            "Report only items NOT covered in your previous run, and update the Living Wiki `[[index]]`."
        ),
        continuity=True,
        recommended_specialist_slug="dreamer",
        skill_names=["knowledge-steward"],
        tool_names=["memory.wiki_write", "memory.mutate"],
        badge="Scheduled · Memory & Wiki",
    ),
    AutomationTemplate(
        id="overnight-experiment-digest",
        name="Overnight Experiment & Screen Digest",
        category="bio_compchem",
        description=(
            "Rank overnight experiment outputs, structure predictions, or assay tables and "
            "record claims in your Knowledge Graph."
        ),
        schedule_expr="daily at 8:00am",
        schedule_label="Daily at 8:00 AM",
        session_mode="fresh",
        prompt=(
            "Scan the workspace for newly completed experiment outputs or predictions since the last run. "
            "Rank the top candidates, record Supports or Contradicts claims in Omnigraph, and write a brief summary."
        ),
        continuity=True,
        recommended_specialist_slug="otium-relaxed",
        skill_names=["omnigraph", "knowledge-steward"],
        tool_names=["memory.graph_record_claim", "memory.wiki_write"],
        badge="Scheduled · Research",
    ),
    AutomationTemplate(
        id="watch-background-job",
        name="Watch Long-Running Job & Alert on Completion",
        category="popular",
        description=(
            "Check a long-running local or remote job every 15 minutes in the same thread "
            "and stop automatically once it finishes."
        ),
        schedule_expr="every 15m",
        schedule_label="Every 15m",
        session_mode="continue",
        prompt=(
            "Check the status of the active job or process in this thread. "
            "If it failed or stalled, report the error immediately. "
            "When it finishes cleanly, summarize the output and call `ops.automation_manage(action='complete')`."
        ),
        continuity=True,
        wake_on_change_only=True,
        recommended_specialist_slug="ambitious-generalist",
        skill_names=["automate"],
        tool_names=["ops.automation_manage"],
        badge="Scheduled · Follow-Up",
    ),
    AutomationTemplate(
        id="watch-slurm-queue",
        name="Submit & Monitor Slurm Jobs over SSH",
        category="hpc_slurm",
        description=(
            "Submit or poll Slurm jobs (sbatch / squeue) on a remote cluster over SSH "
            "and report queue status and completed outputs."
        ),
        schedule_expr="every 15m",
        schedule_label="Every 15m",
        session_mode="fresh",
        command="squeue -u $USER -o '%.18i %.9P %.24j %.8u %.2t %.10M %.6D %R'",
        prompt=(
            "Submit or check Slurm jobs on the configured SSH cluster using `ssh.exec` / `ssh.slurm_status`, "
            "inspect active `squeue` jobs and recent `slurm-*.out` files, and report the queue status and results."
        ),
        continuity=True,
        wake_on_change_only=False,
        recommended_specialist_slug="ambitious-generalist",
        skill_names=["tao-run-on-slurm", "ssh", "automate"],
        tool_names=["ssh.exec", "ssh.slurm_status", "ops.automation_manage"],
        badge="Scheduled · NVIDIA Slurm",
    ),
]


def list_automation_templates() -> list[AutomationTemplate]:
    return list(AUTOMATION_TEMPLATES)


def get_automation_template(template_id: str) -> AutomationTemplate | None:
    needle = (template_id or "").strip().lower()
    for t in AUTOMATION_TEMPLATES:
        if t.id == needle:
            return t
    return None
