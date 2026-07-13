# CLI (`sandwalk`)

Python package for the Sandwalk agent and local server.

```bash
cd cli
uv sync
uv run sandwalk serve
uv run sandwalk --version
uv run pytest tests/ -q
```

### Tests & coverage

```bash
# from monorepo root
pnpm test:cli
pnpm test:cli:coverage
```

Or from `cli/`:

```bash
.venv/bin/python -m pytest tests/ -q -m "not data_smoke and not integration" \
  --cov=agent --cov=agent_server --cov=api --cov=cli --cov=data --cov=kb --cov=models \
  --cov=reports --cov=skills --cov=tools --cov=ui \
  --cov-report=term-missing:skip-covered --cov-fail-under=80
```

Coverage is uploaded to Codecov under flags `agent-cli` and `agent-server`.
See [docs/TESTING.md](../docs/TESTING.md).

Package name: `sandwalk` · version: see repo root `VERSION` / `pyproject.toml`.
