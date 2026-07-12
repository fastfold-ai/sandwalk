# Sandwalk

Local science agents for drug discovery — agent server, web dashboard, and
macOS menubar supervisor in one repo.

**Version:** 0.0.1

## Layout

```
sandwalk/
├── apps/
│   ├── local-web/       # React dashboard (browser)
│   └── sandwalk-mac/    # macOS menubar (owns sandwalk serve)
├── packages/
│   ├── agent-ui-core/   # shared TS types / client contracts
│   └── local-client/    # HTTP/SSE client for the agent server
└── cli/                 # Python package `sandwalk` (`sandwalk serve`)
```

## Development (recommended: menubar)

On macOS, the menubar app starts and stops **API + web UI together** (oMLX-style
unified control — two child processes for now; one process later when the
server serves the built UI).

```bash
pnpm install                 # once
cd apps/sandwalk-mac && swift run
```

- Agent API: http://127.0.0.1:8787  
- Dashboard: http://127.0.0.1:8969  

Do not also run `pnpm dev` while the menubar is running (port conflict on 8969).

### Manual (no menubar)

```bash
# Terminal 1 — API
cd cli && uv sync && uv run sandwalk serve

# Terminal 2 — web
pnpm install && pnpm dev
```

```bash
sandwalk "your research question"
sandwalk serve
sandwalk --version
```

`fastfold` remains a temporary CLI alias for the same entrypoint.

## Environment (menubar)

| Variable | Default | Meaning |
|----------|---------|---------|
| `SANDWALK_HOST` | `127.0.0.1` | API bind host |
| `SANDWALK_PORT` | `8787` | API bind port |
| `SANDWALK_DASHBOARD_HOST` / `PORT` | `127.0.0.1` / `8969` | Web UI bind |
| `SANDWALK_DASHBOARD_URL` | — | Override dashboard host/port |
| `SANDWALK_AUTO_START` | `1` | Start API + web on launch |
| `SANDWALK_REPO_ROOT` | auto | Monorepo root |
| `SANDWALK_AGENT_CLI` | auto (`./cli`) | Path to Python package root |
