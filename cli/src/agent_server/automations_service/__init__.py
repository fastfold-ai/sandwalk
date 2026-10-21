"""Automations & Scheduled Workflows Service package."""

from __future__ import annotations

from agent_server.automations_service.schedule_parser import (
    ParsedSchedule,
    compute_next_run,
    parse_schedule,
)
from agent_server.automations_service.service import (
    AutomationsService,
    automations_output_dir,
)
from agent_server.automations_service.templates import (
    AUTOMATION_TEMPLATES,
    get_automation_template,
    list_automation_templates,
)

__all__ = [
    "AUTOMATION_TEMPLATES",
    "AutomationsService",
    "ParsedSchedule",
    "automations_output_dir",
    "compute_next_run",
    "get_automation_template",
    "list_automation_templates",
    "parse_schedule",
]
