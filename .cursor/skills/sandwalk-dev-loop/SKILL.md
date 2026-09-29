---
name: sandwalk-dev-loop
description: >-
  Run Sandwalk locally from this checkout for development: start the agent API
  (cli/) on :8787, the dashboard UI (Vite / Tauri) on :1420, stop the packaged
  Sandwalk.app that holds the same port, and know what hot-reloads vs. what needs
  a restart. Use when asked to run, restart, or debug the app in dev mode, when a
  port is busy, or when UI/Python changes are not showing up.
---

# Sandwalk dev loop

Two processes, two terminals. The UI never spawns the API.

| Process | Command | Port | Reloads on edit? |
|---------|---------|------|------------------|
| Agent API (`cli/`) | `scripts/dev-api.sh` | 8787 | **No** — Ctrl+C and re-run after editing `cli/src` |
| Dashboard UI | `scripts/dev-ui.sh` (Tauri window) or `scripts/dev-ui.sh web` (browser) | 1420 | TS/React: HMR. Rust in `src-tauri/`: auto rebuild + relaunch |

## Start

```bash
scripts/stop-packaged-app.sh   # only if Sandwalk.app / the menubar server is running (it owns :8787)
scripts/dev-api.sh             # terminal 1
scripts/dev-ui.sh              # terminal 2 (add `web` for browser-only)
curl -fsS http://127.0.0.1:8787/v1/health      # API up?
```

Run long-lived processes in the background and read their output files; do not
block on them. The API prints `Bench runtime started` when ready; the Tauri dev
prints `Finished \`dev\` profile` then `Running …/sandwalk-desktop`.

## Rules

- **Never Start/Restart the menubar "Sandwalk Server" app** when testing checkout
  code — it runs the *bundled* API from the last DMG, not `cli/src`.
- Auth is on: the UI reads the API key from the app's `settings.json`
  (`SANDWALK_SETTINGS_PATH`, set by `dev-api.sh`). A `401` right after an HMR
  reload is transient; persistent 401s mean the key in `settings.json` changed.
- API keys for LLM providers live in `~/.sandwalk/config.json` and
  `settings.json`. Never print them or commit them; redact log lines that
  contain `token=` or `Bearer`.
- `Sandwalk.app` in `~/Applications` is frozen until you rebuild the DMG; use
  the dev loop for UI work, the packaged app only for notifications/signing.
- Native banner-click deep links do not fire in `tauri:dev` (`UN delegate
  skipped (not bundled)`); test those on a signed build.
- In dev builds `window.__sandwalkPerf` exposes render/terminal counters (see
  the `sandwalk-testing` skill); leave `perfCount()` calls in place.

## Common problems

| Symptom | Cause / fix |
|---------|-------------|
| `dev-api.sh` says something listens on :8787 | Packaged menubar server → `scripts/stop-packaged-app.sh`; or an older `sandwalk serve` → `lsof -nP -iTCP:8787 -sTCP:LISTEN` and `kill -INT <pid>` |
| Python change has no effect | API does not hot-reload — restart `dev-api.sh` |
| Models page shows an old catalog | Restart the API (catalog is read at start) |
| Terminal in a split shows a prompt but typing does nothing | PTY socket not open yet; wait for `terminal.wsOpen` counter |
| `Invalid layout total size: 65%, 40%` console warning | Pre-existing, cosmetic (`chat` 65 + `draft-terminal` 40) |
| `Task was destroyed but it is pending!` after `PUT /v1/capy/scope` | Pre-existing on main, Capy scope handler |

## Where things are

- API server: `cli/src/agent_server/` (routes, PTY manager, stores); LLM runtime: `cli/src/agent/`
- UI: `apps/local-web/src/` (`components/agents/` grid + terminal layer, `hooks/`, `lib/`)
- Tauri shell: `apps/local-web/src-tauri/`; menubar helper: `apps/sandwalk-mac/`
- Packaging / signing: `apps/packaging/` (`APPLE-SIGNING.md`)
