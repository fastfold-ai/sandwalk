# fastfold-agent-cli — Project Instructions

## What This Is

fastfold-agent-cli is an autonomous agent for drug discovery research — like Claude Code, but for biology.
It takes natural language questions about compounds/targets/indications and executes
multi-step research workflows using computational biology tools.

## Architecture

**Deep Agents (LangGraph) agentic loop**: Query → model (plans, calls tools, self-corrects, synthesizes) → Report

Built on `deepagents`/LangGraph. A single agentic session orchestrates all domain tools, with native
progressive skill discovery and Programmatic Tool Calling (tools injected as Python callables in the
sandbox). Supports Anthropic and OpenAI (including OpenAI-compatible endpoints via `llm.openai_base_url`).

### Key directories:
```
src/
├── agent/          # Runner, MCP server, system prompt, config
├── tools/          # All research tools (190+), registered via @registry.register()
├── data/           # Data loaders (DepMap, PRISM, L1000, proteomics)
├── models/         # LLM client abstraction
└── ui/             # Interactive terminal
```

## Tool Pattern

Every tool follows this exact pattern:
```python
@registry.register(
    name="category.tool_name",
    description="What this tool does",
    category="category",
    parameters={"param": "description"},
    requires_data=["proteomics"],  # optional
)
def tool_name(param: str = "default", **kwargs) -> dict:
    """Docstring."""
    # ... implementation ...
    return {
        "summary": "Human-readable result summary",
        # ... additional data fields ...
    }
```

Rules:
- Name prefix MUST match category
- Always accept `**kwargs`
- Always return a dict with a `"summary"` key
- Use lazy imports for data loaders inside the function body
- Use `from data.loaders import load_X` pattern

## Commands

```bash
fastfold --version              # Check version
fastfold "your question"        # Single query
fastfold                          # Interactive mode
fastfold tool list                # List all tools
fastfold config set key value     # Set config
fastfold data pull depmap         # Download dataset
pytest tests/ -v                  # Run tests
pip install -e ".[dev]"           # Install for development
```

## Testing

Tests use mocked data loaders — never require real datasets.
Mock pattern: `@patch("tools.module.load_X")` to inject test DataFrames.
