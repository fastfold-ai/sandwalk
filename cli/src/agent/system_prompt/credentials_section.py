"""Prompt section listing configured integration env var *names* (never values)."""

from __future__ import annotations


def build_credentials_section() -> str:
    """Tell the agent which Integrations credentials are already in process env."""
    try:
        from agent.config import listed_integration_env_vars, sync_sandwalk_path_env

        sync_sandwalk_path_env(force=True)
        names = listed_integration_env_vars()
    except Exception:
        return ""

    path_vars = ["SANDWALK_CONFIG_DIR", "SANDWALK_SKILLS_DIR", "SANDWALK_SESSION_WORKSPACE"]
    parts = [
        "\n## Credentials & paths (host shell)\n",
        "- Integrations keys are mirrored into the host process environment for "
        "`shell.run` / skill scripts. Prefer `printenv NAME` to check presence; "
        "never paste secret values into the chat.\n",
        "- Skill scripts: `$SANDWALK_SKILLS_DIR/<skill>/scripts/...` "
        "(or the absolute path from the skills listing).\n",
        "- Config root: `$SANDWALK_CONFIG_DIR` (e.g. `config.json`).\n",
        "- Session downloads/writes: use the Session workspace path above "
        "(also `$SANDWALK_SESSION_WORKSPACE` when set).\n",
    ]
    if names:
        listed = ", ".join(f"`{n}`" for n in names)
        parts.append(f"- **Configured env vars (present):** {listed}\n")
        parts.append(
            "- Do **not** ask the user for a `.env` or to export these keys unless "
            "a skill script fails with an explicit auth error after you ran it.\n"
        )
    else:
        parts.append(
            "- No Integrations API keys are currently in the host environment. "
            "If a skill needs one, ask the user to set it under Integrations "
            "(or export the env var) before retrying.\n"
        )
    # Mention path vars so the agent knows the names even when workspace is empty.
    path_line = ", ".join(f"`{n}`" for n in path_vars)
    parts.append(f"- Path helpers: {path_line}\n")
    return "".join(parts)
