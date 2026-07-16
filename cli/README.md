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

| Command | What | Size / time |
|---------|------|-------------|
| `pnpm test:cli:functional` | Offline real-process smoke | ~10–20 tests, ~10s |
| `pnpm test:cli:all` | Full CLI integration (network + chat) | minutes; uses `~/.sandwalk` keys |
| `pnpm test:cli:unit` | **Full** mocked unit suite (not a smoke) | ~2400 tests, several minutes |
| `pnpm test:cli` | CI mix: unit + offline functional | same as unit + a bit |

```bash
pnpm test:cli:functional   # quick smoke
pnpm test:cli:unit         # full unit suite (~2400)
pnpm test:cli:all          # integration only
pnpm test:cli:coverage     # CI coverage gate
```

Or from `cli/`:

```bash
.venv/bin/python -m pytest tests/ -q \
  --cov=agent --cov=agent_server --cov=api --cov=cli --cov=data --cov=kb --cov=models \
  --cov=reports --cov=skills --cov=tools --cov=ui \
  --cov-report=term-missing:skip-covered --cov-fail-under=80
```

Coverage is uploaded to Codecov under flags `agent-cli` and `agent-server`.
See [docs/TESTING.md](../docs/TESTING.md).

Package name: `sandwalk` · version: see repo root `VERSION` / `pyproject.toml`.
