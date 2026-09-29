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

## Updates

Desktop builds use `tauri-plugin-updater` against GitHub Releases
`…/releases/latest/download/latest.json`. General → **Check again** / **Update now**
downloads the signed nested `.app.tar.gz` and relaunches. Packaging details:
[`apps/packaging/README.md`](../packaging/README.md).

## Build (DMG)

One script builds the Tauri client, nests Sandwalk Server, and writes a DMG:

```bash
./apps/packaging/package-macos-dmg.sh
# optional local install:
INSTALL=1 ./apps/packaging/package-macos-dmg.sh
```

Output: `apps/packaging/dist/Sandwalk-<version>-macos-arm64.dmg`

Apple Developer ID + local/CI signing: [`apps/packaging/APPLE-SIGNING.md`](../packaging/APPLE-SIGNING.md).

Users drag **Sandwalk.app** into Applications. Opening Sandwalk auto-starts the nested
helper if the control plane is not already up.

## Control plane

Menubar listens on `127.0.0.1:18787` (or an ephemeral port) and writes:

`~/Library/Application Support/Sandwalk/control.json` — `host`, `port`, `token`, `api_base`.

Auth: `Authorization: Bearer <token>` (file mode `0600`).

## Voice input

Local speech-to-text for the composer (not available in the browser SPA).

| Piece | Detail |
|-------|--------|
| Engine | `sandwalk-stt` (Whisper Base English via `whisper-rs`) inside the Tauri process |
| Setup | Dashboard → **Voice**: install model → mic check → composer mic unlocks |
| Privacy | Mic audio stays in memory while recording; no agent-server / cloud STT |
| Models dir | macOS `~/Library/Application Support/Sandwalk/models/`; Windows `%APPDATA%\Sandwalk\models\`; Linux `~/.config/sandwalk/models/` |
| Packaging | `NSMicrophoneUsageDescription` + `com.apple.security.device.audio-input` |
| Platforms | macOS 12+ Apple Silicon; Windows 10 22H2 / 11 x64 |

Composer: mic before Send → listening bar (live mic levels) → confirm inserts text into the draft. Escape cancels.

## Menubar actions

| Item | Behavior |
|------|----------|
| **New Agent** | Creates a session, opens Sandwalk.app |
| **Open Sandwalk** | Focuses/opens the Tauri client |
| **Server Settings…** | Swift Settings (Server + General only) |
| **Stop / Restart / Quit** | Process supervision |

## App + File menus (multi-window)

The Tauri client supports multiple windows in one process (Cursor-style). Each window is an independent SPA instance bound to a backend via `__SANDWALK_HTTP__` inject, `?sw_http=` / `?sw_key=` bootstrap, and per-window `window.name` (shared `localStorage` is not used for remote binds, so a remote window cannot overwrite the local main window).

On macOS the **first** submenu is the app menu (named **Sandwalk**). New Window lives under **File**.

| Menu | Item | Behavior |
|------|------|----------|
| **Sandwalk** | About Sandwalk | Native about panel |
| **Sandwalk** | Check for Updates… | Opens Dashboard → General and runs the update check |
| **Sandwalk** | Server Settings… | Opens the nested **Sandwalk Server** helper Settings UI (`sandwalk://settings/general`) |
| **File** | New Window (`⇧⌘N`) | New window on the Welcome / connection chooser (does not restore last session or copy the focused remote) |
| **File** | New Window (Remote)… | Dialog for server URL + optional API key; auto-scans LAN `:8787`/`:8789`/`:8790` via `/v1/discover` |
| **File** | Open Recent | MRU **window snapshots** (`window-recents.json`: url + last route + title); keys in SPA remembered-auth |
| **File** | Close Window | `main` **hides**; extra `client-*` windows **destroy** |

Dock right-click / Mission Control lists every open window using the **current chat or page title** (Cursor-style). Remote windows append ` — host:port`.

### Manual verification

1. File → New Window → Welcome Home chooser (Connect locally / Open remote); cold-start of the app still restores the last session.
2. File → New Window (Remote) → LAN scan lists nearby Sandwalk hosts (OS/device label); pick one or type URL + key → only that window talks to remote; `main` unchanged. Expose the other machine via Server Settings → Network (Allow Remote) + Security (API key), or CLI: `sandwalk auth enable` + `sandwalk serve --host 0.0.0.0`. macOS may prompt for Local Network access.
3. Quit/reopen → Open Recent lists windows by last title (not just host); choosing one reopens that snapshot (same route when possible) or focuses if still open.
4. Close a secondary window (destroys); Close on `main` (hides).
5. Dock right-click shows local + remote titles; selecting one focuses it.
6. General → Change server in `main` retargets that window only (siblings keep inject).

## QA matrix

| Host | Chats / Agent settings | Server Status | Desktop General |
|------|------------------------|---------------|-----------------|
| Browser | Yes | Hidden | Hidden |
| Packaged Sandwalk.app | Yes | Via nested helper | Shown |
| Helper only (no window) | — | Tray + Server Settings | Swift Settings |

Confirm: close Sandwalk window → agent stays up; **Quit Sandwalk Server** on the tray stops it.
