"""Tool catalog + enable/disable management for the agent server."""

from __future__ import annotations

from agent.config import Config
from agent_server.models import (
    ToolBatchAction,
    ToolBatchActionResponse,
    ToolList,
    ToolSummary,
    UpdateToolRequest,
)


def _tool_status(tool) -> str:
    from tools import EXPERIMENTAL_CATEGORIES

    if tool.name == "claude.code":
        return "guarded"
    if tool.category in EXPERIMENTAL_CATEGORIES:
        return "experimental"
    return "stable"


class ToolsService:
    def _summary(self, tool, hidden: set[str]) -> ToolSummary:
        return ToolSummary(
            id=tool.name,
            name=tool.name,
            category=str(tool.category or "general"),
            status=_tool_status(tool),  # type: ignore[arg-type]
            description=str(tool.description or ""),
            requires_data=list(tool.requires_data or []),
            enabled=tool.name not in hidden,
        )

    def list_tools(self, *, enabled_only: bool = False) -> ToolList:
        from tools import ensure_loaded, registry, tool_load_errors

        ensure_loaded()
        cfg = Config.load()
        hidden = set(cfg.hidden_tools())
        items: list[ToolSummary] = []
        for tool in registry.list_tools():
            summary = self._summary(tool, hidden)
            if enabled_only and not summary.enabled:
                continue
            items.append(summary)
        return ToolList(
            data=items,
            count=len(items),
            categories=registry.categories(),
            load_errors=tool_load_errors(),
        )

    def get_tool(self, tool_id: str) -> ToolSummary | None:
        from tools import ensure_loaded, registry

        ensure_loaded()
        tool = registry.get_tool(str(tool_id or "").strip())
        if tool is None:
            return None
        hidden = set(Config.load().hidden_tools())
        return self._summary(tool, hidden)

    def set_tool_enabled(self, tool_id: str, enabled: bool) -> ToolSummary:
        from tools import ensure_loaded, registry

        ensure_loaded()
        target = str(tool_id or "").strip()
        if not target:
            raise ValueError("tool_id is required.")
        if registry.get_tool(target) is None:
            raise KeyError(target)
        cfg = Config.load()
        cfg.set_tool_hidden(target, hidden=not enabled)
        cfg.save()
        result = self.get_tool(target)
        assert result is not None
        return result

    def update_tool(self, tool_id: str, payload: UpdateToolRequest) -> ToolSummary:
        if payload.enabled is None:
            raise ValueError("enabled is required.")
        return self.set_tool_enabled(tool_id, bool(payload.enabled))

    def batch_action(
        self, action: ToolBatchAction, ids: list[str]
    ) -> ToolBatchActionResponse:
        from tools import ensure_loaded, registry

        ensure_loaded()
        enabled = action == "enable"

        # De-dupe while preserving order.
        seen: set[str] = set()
        targets: list[str] = []
        for raw in ids:
            tool_id = str(raw or "").strip()
            if not tool_id or tool_id in seen:
                continue
            seen.add(tool_id)
            targets.append(tool_id)

        cfg = Config.load()
        succeeded: list[str] = []
        failed: list[str] = []
        for tool_id in targets:
            if registry.get_tool(tool_id) is None:
                failed.append(tool_id)
                continue
            cfg.set_tool_hidden(tool_id, hidden=not enabled)
            succeeded.append(tool_id)
        cfg.save()

        total = len(targets)
        return ToolBatchActionResponse(
            ok=not failed,
            action=action,
            requested=total,
            succeeded=succeeded,
            failed=failed,
            summary=f"{action.title()} completed: {len(succeeded)}/{total} succeeded.",
        )
