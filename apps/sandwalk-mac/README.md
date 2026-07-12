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

On launch (default `SANDWALK_AUTO_START=1`) the menu bar starts API + web.
Use **Start Sandwalk** / **Stop Sandwalk**, **Open Web Dashboard** (⌘O), or **Quit**.

Do **not** run a standalone `pnpm dev` in another terminal while the menubar is
supervising — it will fight over port 8969.

## Env

| Variable | Default | Meaning |
|----------|---------|---------|
| `SANDWALK_HOST` / `SANDWALK_PORT` | `127.0.0.1` / `8787` | API bind |
| `SANDWALK_DASHBOARD_HOST` / `SANDWALK_DASHBOARD_PORT` | `127.0.0.1` / `8969` | Web bind |
| `SANDWALK_DASHBOARD_URL` | — | Override host/port from a full URL |
| `SANDWALK_AUTO_START` | `1` | Start both on launch (`0` to wait) |
| `SANDWALK_REPO_ROOT` | auto | Monorepo root (`package.json` + `cli/`) |
| `SANDWALK_AGENT_CLI` | `./cli` | Python package root |
| `SANDWALK_SERVE_BIN` | — | Absolute path to `sandwalk` binary |

Logs: `~/Library/Application Support/Sandwalk/logs/{server,web}.log`
