# Sandwalk macOS menubar (v1)

Menubar app that owns `sandwalk serve` (Start / Stop / health) and opens the
web dashboard in the browser.

## Run (from monorepo root)

```bash
pnpm install && pnpm dev
cd apps/sandwalk-mac && swift run
```

Auto-discovers the Python package at `../../cli`. Override with
`SANDWALK_AGENT_CLI=/path/to/cli`.

See the [repo README](../../README.md) for env vars and architecture.
