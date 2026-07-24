"""Default config values for sandbox, agent runtime, enterprise, knowledge, ops."""

from pathlib import Path

from .constants import CONFIG_DIR

DEFAULTS_AGENT = {
    "sandbox.timeout": 30,
    "sandbox.output_dir": str(Path.cwd() / "outputs"),
    "sandbox.max_retries": 2,
    # Deepagents filesystem/execute backend: "builtin" (local FilesystemBackend)
    # or "modal" (langchain-modal ModalSandbox). Domain tools stay on the host.
    "sandbox.backend": "builtin",
    "sandbox.modal_app": "sandwalk",
    "sandbox.cpu_image": "python:3.12-slim",
    "sandbox.gpu_image": "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime",
    "sandbox.pip_packages": "pandas,numpy,scipy,scikit-learn,matplotlib,seaborn",
    "sandbox.compute_type": "cpu",
    "sandbox.gpu_class": "T4",
    "sandbox.cpu_cores": 2.0,
    "sandbox.ram_gb": 8.0,
    "sandbox.idle_ttl_seconds": 600,

    "agent.max_iterations": 3,
    # Tool-calling strategy for the deepagents runtime: "ptc" (Programmatic Tool
    # Calling, default — domain tools are injected as Python callables inside
    # run_python and the model invokes them in code, with only a compact catalog
    # + search_tools in context) or "native" (each domain tool exposed as its own
    # LangChain tool schema). PTC significantly reduces per-call input tokens and
    # removes the OpenAI tool-count ceiling. Set to "native" to restore per-tool
    # schemas.
    "agent.tool_mode": "ptc",
    # Tool-call rendering (deepagents runtime only). When True, the most recent
    # `agent.tool_trace_detail_limit` tool calls in a consecutive batch stay in
    # full detail (name, args, output) and older ones collapse progressively to a
    # one-line, still named "✓ name (Xs)" entry as newer calls complete — the
    # current/last call stays detailed while earlier ones compact away. Errors
    # always show in full. Set False to show every tool call fully verbose.
    "agent.group_tool_traces": True,
    # Trailing window: how many most-recent tool calls keep full detail before
    # older ones collapse to compact named lines. 1 = only the last call full.
    "agent.tool_trace_detail_limit": 1,
    # Max model↔tool loop iterations for the deepagents (LangGraph) runtime.
    # LangGraph requires a finite cap; default is effectively unlimited for
    # long training / fold / download workflows. Override via CLI:
    #   sandwalk config set agent.recursion_limit 0   # unlimited
    # or Dashboard → Agent → Runtime in the Mac/web app.
    "agent.recursion_limit": 100_000,
    # Legacy soft turn budget (only used if recursion_limit is explicitly cleared).
    "agent.max_sdk_turns": 500,
    "agent.enable_experimental_tools": False,
    "skills.allow_agent_install": True,
    "agent.observer_model": None,
    "agent.executor_max_retries": 2,
    "agent.executor_loop_limit": 50,
    "agent.observer_confidence_threshold": 0.8,
    "agent.synthesis_max_tokens": 8192,
    "agent.enforce_grounded_synthesis": True,
    "agent.enforce_claim_content_validation": True,
    "agent.confidence_scoring_enabled": True,
    "agent.min_step_success_rate": 0.5,
    "agent.require_key_evidence_section": True,
    "agent.allow_creative_hypotheses": True,
    "agent.max_hypotheses": 3,
    "agent.grounding_repair_retries": 1,
    "agent.log_evidence_store": True,
    "agent.memory_retrieval_enabled": True,
    "agent.memory_retrieval_limit": 3,
    "agent.verifier_model": None,
    "agent.verifier_provider": None,
    "agent.verifier_repair_retries": 1,
    "agent.quality_gate_enabled": True,
    "agent.quality_gate_strict": False,
    "agent.quality_gate_repair_retries": 1,
    "agent.quality_gate_repair_non_strict": False,
    "agent.quality_gate_min_next_steps": 2,
    "agent.quality_gate_max_next_steps": 3,
    "agent.synthesis_style": "standard",
    "agent.profile": "research",
    # Active specialist slug for interactive/batch CLI runs (empty = global).
    "agent.cli_specialist": "",
    # CLI-only sandbox preference (Local vs Modal). Independent of web
    # dashboard ``sandbox.backend`` — see agent.sandbox_manage.
    "agent.cli_sandbox": "builtin",
    "agent.enable_claude_code_tool": False,
    "agent.parallel_default_count": 3,
    "agent.parallel_auto_suggest": True,
    "agent.parallel_max_threads": 5,
    "agent.background_watch_timeout_s": 7200,
    "agent.interrupt_drain_timeout_s": 10,
    "agent.planner_max_tools": 90,
    "agent.planner_compact_tool_descriptions": True,
    # True = Plan mode (author plans/*.md); False = Agent mode (execute).
    "agent.plan_preview": False,
    "agent.tool_health_enabled": True,
    "agent.tool_health_fail_threshold": 2,
    "agent.tool_health_failure_window_s": 1800,
    "agent.tool_health_suppress_seconds": 900,
    "agent.preflight_validation_enabled": True,
    "agent.skills.max_catalog_entries": 250,
    "agent.skills.max_active": 6,
    "agent.skills.max_prompt_chars": 120000,
    "agent.skills.catalog_description_chars": 140,
    "agent.skills.index_snippet_chars": 8000,

    "enterprise.enforce_policy": False,
    "enterprise.audit_enabled": True,
    "enterprise.audit_dir": str(CONFIG_DIR / "audit"),
    "enterprise.blocked_tools": "",
    "enterprise.blocked_categories": "",
    "enterprise.require_tool_allowlist": False,
    "enterprise.tool_allowlist": "",
    "enterprise.max_cost_usd_per_query": 0.0,

    "knowledge.enable_substrate": True,
    "knowledge.auto_ingest_evidence": True,
    "knowledge.substrate_path": str(CONFIG_DIR / "knowledge" / "substrate.json"),
    "knowledge.schema_monitor_enabled": False,

    "ops.base_dir": str(CONFIG_DIR / "ops"),
    "install.uv_flavor": None,
}
