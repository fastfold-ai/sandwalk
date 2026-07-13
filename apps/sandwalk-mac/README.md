# Sandwalk macOS menubar

Menubar app that owns **both** the agent API (`sandwalk serve`) and the web
dashboard (Vite) — Start / Stop / Quit together, like oMLX’s unified control.

| Service | Default | Health |
|---------|---------|--------|
| Agent API | `127.0.0.1:8787` | `GET /v1/health` |
| Web UI | `127.0.0.1:8969` | HTTP GET `/` |

## Run (from monorepo root)

```bash
pnpm install   # once — web dashboard deps
cd apps/sandwalk-mac && swift run
```

On launch (default auto-start) the menu bar starts API + web.
Use **Start Sandwalk** / **Stop Sandwalk**, **Open Web Dashboard** (⌘O), or **Quit**.

**Settings…** opens a real Settings window (Server + Security). Clicking the Dock
icon (while Settings is open) or Launchpad / Applications relaunches into Settings.

## Install as a Mac app (Launchpad / Applications)

```bash
cd apps/sandwalk-mac
./scripts/package-app.sh
open ~/Applications/Sandwalk.app
```

This builds `Sandwalk.app`, installs it to `~/Applications`, and gives it the
Sandwalk mark icon. Prefer this over bare `swift run` so the app shows up in
Finder / Launchpad like a normal Mac app.

Persisted under `~/Library/Application Support/Sandwalk/settings.json` (`server` + `auth` sections).

**Settings…** (menubar) manages:

- **Server** — API / dashboard ports, allow remote connections (`0.0.0.0`), start on launch. Apply restarts both services.
- **Security** — API key generate / show / copy / reset, enable auth. Same `settings.json` as `sandwalk auth`.

Do **not** run a standalone `pnpm dev` in another terminal while the menubar is
supervising — it will fight over the dashboard port.

## Env (optional overrides)

Env wins over `settings.json` when set at launch:

| Variable | Default | Meaning |
|----------|---------|---------|
| `SANDWALK_HOST` / `SANDWALK_PORT` | from settings / `127.0.0.1` / `8787` | API bind |
| `SANDWALK_DASHBOARD_HOST` / `SANDWALK_DASHBOARD_PORT` | from settings / `127.0.0.1` / `8969` | Web bind |
| `SANDWALK_DASHBOARD_URL` | — | Override host/port from a full URL |
| `SANDWALK_AUTO_START` | from settings / `1` | Start both on launch (`0` to wait) |
| `SANDWALK_REPO_ROOT` | auto | Monorepo root (`package.json` + `cli/`) |
| `SANDWALK_AGENT_CLI` | `./cli` | Python package root |
| `SANDWALK_SERVE_BIN` | — | Absolute path to `sandwalk` binary |

Logs: `~/Library/Application Support/Sandwalk/logs/{server,web}.log`
