# sandwalk — Project Instructions

## What This Is

Sandwalk is an open, self-hosted agent harness for ambitious work — hard
scientific research and any other domain the user directs it toward. It ships a
deep science toolkit (compounds, targets, structures, omics, clinical, literature)
and grows via skills/MCPs. Natural language in; multi-step workflows out.

## Architecture

**Deep Agents (LangGraph) agentic loop**: Query → model (plans, calls tools, self-corrects, synthesizes) → Report

Built on `deepagents`/LangGraph. A single agentic session orchestrates all domain tools, with native
progressive skill discovery and Programmatic Tool Calling (tools injected as Python callables in the
sandbox). Supports Anthropic and OpenAI (including OpenAI-compatible endpoints via `llm.openai_base_url`).

### Key directories:
```
src/
├── agent/          # Runner, MCP server, system prompt, config
├── agent_server/   # Local FastAPI server for the web UI / Mac app
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
sandwalk --version              # Check version
sandwalk "your question"        # Single query
sandwalk                        # Interactive mode
sandwalk tool list              # List all tools
sandwalk config set key value   # Set config
sandwalk data pull depmap       # Download dataset
pytest tests/ -v                # Run tests
ruff check src                  # Lint
mypy                            # Typecheck (scoped packages in pyproject.toml)
pip install -e ".[dev]"         # Install for development
```

## Testing

Tests use mocked data loaders — never require real datasets.
Mock pattern: `@patch("tools.module.load_X")` to inject test DataFrames.

## Linting

**ruff** (`E,W,F,I,B,C4,UP`, `E501` ignored) + **mypy** (strict, expanding package by package).
Formatter width is `line-length = 100`; long lines are a formatting preference, not a hard reject.

Prefer cohesive modules. Review unusually large files for mixed responsibilities in PR review, but do **not** split files based only on line count.
