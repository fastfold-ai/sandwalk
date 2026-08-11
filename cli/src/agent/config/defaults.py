"""Merged config defaults and per-profile presets."""

from .defaults_agent import DEFAULTS_AGENT
from .defaults_llm import DEFAULTS_LLM

DEFAULTS = {**DEFAULTS_LLM, **DEFAULTS_AGENT}

AGENT_PROFILE_PRESETS = {
    "research": {
        "agent.enforce_grounded_synthesis": True,
        "agent.enforce_claim_content_validation": True,
        "agent.require_key_evidence_section": True,
        "agent.allow_creative_hypotheses": True,
        "agent.quality_gate_enabled": True,
        "agent.quality_gate_strict": False,
        "agent.quality_gate_repair_retries": 1,
        "agent.quality_gate_repair_non_strict": False,
        "agent.synthesis_style": "standard",
        "agent.memory_retrieval_enabled": True,
        "agent.enable_claude_code_tool": False,
        "enterprise.enforce_policy": False,
        "enterprise.blocked_tools": "",
        "enterprise.blocked_categories": "",
        "enterprise.require_tool_allowlist": False,
    },
    "enterprise": {
        "agent.enforce_grounded_synthesis": True,
        "agent.enforce_claim_content_validation": True,
        "agent.require_key_evidence_section": True,
        "agent.allow_creative_hypotheses": False,
        "agent.quality_gate_enabled": True,
        "agent.quality_gate_strict": True,
        "agent.quality_gate_repair_retries": 2,
        "agent.quality_gate_repair_non_strict": True,
        "agent.synthesis_style": "standard",
        "agent.memory_retrieval_enabled": True,
        "agent.enable_claude_code_tool": False,
        "enterprise.enforce_policy": True,
        "enterprise.blocked_tools": "shell.run,files.delete_file,claude.code",
        "enterprise.blocked_categories": "",
        "enterprise.require_tool_allowlist": False,
    },
    "pharma": {
        "agent.enforce_grounded_synthesis": True,
        "agent.enforce_claim_content_validation": True,
        "agent.require_key_evidence_section": True,
        "agent.allow_creative_hypotheses": False,
        "agent.quality_gate_enabled": True,
        "agent.quality_gate_strict": True,
        "agent.quality_gate_repair_retries": 2,
        "agent.quality_gate_repair_non_strict": True,
        "agent.quality_gate_min_next_steps": 3,
        "agent.quality_gate_max_next_steps": 3,
        "agent.synthesis_style": "pharma",
        "agent.memory_retrieval_enabled": True,
        "agent.enable_claude_code_tool": False,
        "enterprise.enforce_policy": False,
        "enterprise.blocked_tools": "",
        "enterprise.blocked_categories": "",
        "enterprise.require_tool_allowlist": False,
    },
}
