"""Core Tool/ToolRegistry data structures, split out of tools/__init__.py."""

from collections.abc import Callable
from dataclasses import dataclass, field

from rich.table import Table

EXPERIMENTAL_CATEGORIES = frozenset({"compute", "cro"})


@dataclass
class Tool:
    """A registered tool that the agent can invoke."""
    name: str                  # e.g., "target.neosubstrate_score"
    description: str           # Human-readable description
    category: str              # e.g., "target", "structure", "chemistry"
    function: Callable         # The actual Python function
    parameters: dict = field(default_factory=dict)  # Parameter descriptions
    requires_data: list = field(default_factory=list)  # Required datasets
    usage_guide: str = ""      # When/why to use this tool (injected into planner prompt)

    def run(self, **kwargs):
        """Execute the tool."""
        return self.function(**kwargs)


class ToolRegistry:
    """Central registry of all available tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, description: str, category: str,
                 parameters: dict = None, requires_data: list = None,
                 usage_guide: str = ""):
        """Decorator to register a function as a tool."""
        def decorator(func):
            self._tools[name] = Tool(
                name=name,
                description=description,
                category=category,
                function=func,
                parameters=parameters or {},
                requires_data=requires_data or [],
                usage_guide=usage_guide,
            )
            return func
        return decorator

    def get_tool(self, name: str) -> Tool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(self, category: str = None) -> list[Tool]:
        """List all tools, optionally filtered by category."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return sorted(tools, key=lambda t: t.name)

    def list_tools_table(self) -> Table:
        """Render tool list as a rich table."""
        table = Table(title="ct Tools")
        table.add_column("Tool", style="cyan")
        table.add_column("Status")
        table.add_column("Description")
        table.add_column("Data Required", style="dim")

        for tool in self.list_tools():
            data_str = ", ".join(tool.requires_data) if tool.requires_data else "-"
            if tool.name == "claude.code":
                status = "[yellow]guarded (opt-in)[/yellow]"
            elif tool.category in EXPERIMENTAL_CATEGORIES:
                status = "[yellow]experimental / TODO[/yellow]"
            else:
                status = "[green]stable[/green]"
            table.add_row(tool.name, status, tool.description, data_str)

        return table

    def categories(self) -> list[str]:
        """List all tool categories."""
        return sorted({t.category for t in self._tools.values()})

    def tool_descriptions_for_llm(
        self,
        exclude_categories: set[str] | None = None,
        exclude_tools: set[str] | None = None,
    ) -> str:
        """Generate tool descriptions for the LLM planner."""
        exclude_categories = exclude_categories or set()
        exclude_tools = exclude_tools or set()
        lines = []
        for cat in self.categories():
            if cat in exclude_categories:
                continue
            cat_tools = [t for t in self.list_tools(cat) if t.name not in exclude_tools]
            if not cat_tools:
                continue
            lines.append(f"\n## {cat}")
            for tool in cat_tools:
                params = ", ".join(f"{k}: {v}" for k, v in tool.parameters.items())
                lines.append(f"- **{tool.name}**({params}): {tool.description}")
                if tool.usage_guide:
                    lines.append(f"  USE WHEN: {tool.usage_guide}")
                if tool.category in EXPERIMENTAL_CATEGORIES:
                    lines.append("  NOTE: Experimental/TODO category. Outputs may be placeholder or limited.")
        return "\n".join(lines)


# Global registry instance
registry = ToolRegistry()
