# Sandwalk

Local science agents for drug discovery — agent server, web dashboard, and
macOS menubar supervisor in one repo.

## Layout

```
sandwalk/
├── apps/
│   ├── local-web/       # React dashboard (browser)
│   └── sandwalk-mac/    # macOS menubar (owns fastfold serve)
├── packages/
│   ├── agent-ui-core/   # shared TS types / client contracts
│   └── local-client/    # HTTP/SSE client for the agent server
└── cli/                 # Python agent + `fastfold serve` (FastAPI)
```

## Development

```bash
# Terminal 1 — menubar owns the agent server (macOS)
cd apps/sandwalk-mac && swift run

# Or Terminal 1 — server only
cd cli && uv sync && uv run fastfold serve

# Terminal 2 — web dashboard
pnpm install
pnpm dev
```

- Dashboard: http://127.0.0.1:8969  
- Agent API: http://127.0.0.1:8787  

Menubar **Open Web Dashboard** opens the Vite app. Production will serve the
built UI from the agent server (same process) in a later step.

## Environment (menubar)

| Variable | Default | Meaning |
|----------|---------|---------|
| `SANDWALK_HOST` | `127.0.0.1` | Bind host |
| `SANDWALK_PORT` | `8787` | Bind port |
| `SANDWALK_DASHBOARD_URL` | `http://127.0.0.1:8969` | Dashboard URL |
| `SANDWALK_AUTO_START` | `1` | Start server on launch |
| `SANDWALK_AGENT_CLI` | auto (`./cli`) | Path to Python package root |

## Status

Migrated from `fastfold-agent-cli` + `fastfold-agent-ui`. The CLI package name
and `fastfold` entrypoint remain for compatibility while we unify branding.
