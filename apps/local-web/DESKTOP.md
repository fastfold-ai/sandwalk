# Sandwalk Desktop (Tauri)

Tauri wraps this SPA in a native Mac window. It does **not** spawn `sandwalk serve`.
The nested **Sandwalk Server** helper (Swift menubar) remains the process supervisor and
keeps the agent running with no windows open.

## Architecture

| Piece | Role |
|-------|------|
| **Sandwalk.app (Tauri)** | User-facing client (Dock / Launchpad); `invoke` → control plane |
| **Sandwalk Server.app** | Menubar tray; Start/Stop/Restart; owns API; nested at `Contents/Helpers/` in the DMG |
| **Browser** | Same SPA for development; no server process controls |

## Dev

1. Start the menubar helper (or ensure the control plane is up):

```bash
cd apps/sandwalk-mac && ./scripts/package-app.sh && open ~/Applications/Sandwalk\ Server.app
```

2. From this package:

```bash
pnpm --filter @sandwalk/agent-local-web tauri:dev
```

Vite for Tauri uses port **1420** (menubar Development mode still uses **8969**).

## Build (DMG)

One script builds the Tauri client, nests Sandwalk Server, and writes a DMG:

```bash
./apps/packaging/package-macos-dmg.sh
# optional local install:
INSTALL=1 ./apps/packaging/package-macos-dmg.sh
```

Output: `apps/packaging/dist/Sandwalk-<version>-macos-arm64.dmg`

Users drag **Sandwalk.app** into Applications. Opening Sandwalk auto-starts the nested
helper if the control plane is not already up.

## Control plane

Menubar listens on `127.0.0.1:18787` (or an ephemeral port) and writes:

`~/Library/Application Support/Sandwalk/control.json` — `host`, `port`, `token`, `api_base`.

Auth: `Authorization: Bearer <token>` (file mode `0600`).

## Menubar actions

| Item | Behavior |
|------|----------|
| **New Agent** | Creates a session, opens Sandwalk.app |
| **Open Sandwalk** | Focuses/opens the Tauri client |
| **Server Settings…** | Swift Settings (Server + General only) |
| **Stop / Restart / Quit** | Process supervision |

## QA matrix

| Host | Chats / Agent settings | Server Status | Desktop General |
|------|------------------------|---------------|-----------------|
| Browser | Yes | Hidden | Hidden |
| Packaged Sandwalk.app | Yes | Via nested helper | Shown |
| Helper only (no window) | — | Tray + Server Settings | Swift Settings |

Confirm: close Sandwalk window → agent stays up; **Quit Sandwalk Server** on the tray stops it.
