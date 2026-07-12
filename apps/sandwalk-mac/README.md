# Sandwalk macOS menubar (v1)

Menubar app that owns `fastfold serve` (Start / Stop / health) and opens the
web dashboard in the browser.

## Run (from monorepo root)

```bash
# Web UI (optional for Open Dashboard)
pnpm install && pnpm dev

# Menubar
cd apps/sandwalk-mac
swift run
```

Auto-discovers the Python package at `../../cli`. Override with
`SANDWALK_AGENT_CLI=/path/to/cli`.

See the [repo README](../../README.md) for env vars and architecture.
