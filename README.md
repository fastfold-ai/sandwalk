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

## Development

```bash
# Terminal 1 — menubar owns the agent server (macOS)
cd apps/sandwalk-mac && swift run

# Or Terminal 1 — server only
cd cli && uv sync && uv run sandwalk serve

# Terminal 2 — web dashboard
pnpm install
pnpm dev
```

- Dashboard: http://127.0.0.1:8969  
- Agent API: http://127.0.0.1:8787  

```bash
sandwalk "your research question"
sandwalk serve
sandwalk --version
```

`fastfold` remains a temporary CLI alias for the same entrypoint.

## Environment (menubar)

| Variable | Default | Meaning |
|----------|---------|---------|
| `SANDWALK_HOST` | `127.0.0.1` | Bind host |
| `SANDWALK_PORT` | `8787` | Bind port |
| `SANDWALK_DASHBOARD_URL` | `http://127.0.0.1:8969` | Dashboard URL |
| `SANDWALK_AUTO_START` | `1` | Start server on launch |
| `SANDWALK_AGENT_CLI` | auto (`./cli`) | Path to Python package root |
