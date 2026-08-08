# Sandwalk macOS packaging

Builds a single installable DMG:

```text
Sandwalk.app                                 ← Tauri client (what users open)
└── Contents/Helpers/Sandwalk Server.app     ← menubar supervisor (no Dock icon)
```

## Prerequisites

- Full **Xcode** (Swift helper) and Rust (Tauri client)
- **`cmake`** — `brew install cmake`. Required by `whisper-rs-sys`, which builds
  whisper.cpp for the STT crate; without it the Tauri build fails with
  ``is `cmake` not installed?``
- `pnpm install` at the repo root

## Build

From the repo root:

```bash
./apps/packaging/package-macos-dmg.sh
```

Or:

```bash
pnpm --filter @sandwalk/agent-local-web package:dmg
```

Artifacts land in `apps/packaging/dist/`:

- `Sandwalk-<version>-macos-arm64.dmg`
- `stage/Sandwalk.app` (assembled app before DMG)

Install for local QA:

```bash
INSTALL=1 ./apps/packaging/package-macos-dmg.sh
```

Reuse an existing Tauri bundle (faster iteration on nesting):

```bash
SKIP_TAURI=1 ./apps/packaging/package-macos-dmg.sh
```

## Rebuild and relaunch (local dev loop)

```bash
pnpm relaunch:mac
# or: ./apps/packaging/relaunch-macos-app.sh
```

Stops the running app, rebuilds and reinstalls, relaunches, then waits for the whole
supervised chain (client → helper → agent) to come up.

Two details the script handles that a plain rebuild does not:

- **Orphaned agents.** The agent can outlive its parent and keep holding both the API
  port and the SQLite lock, so an immediate restart fails with `Another Sandwalk
  server already has this database open`. The script waits for a graceful exit,
  force-kills whatever still holds the port or database, and refuses to continue if
  either is still held. It stops **twice** — once up front and again right before
  launching — because the build takes long enough for a start-on-launch relaunch to
  slip in and get half-killed by the install step.
- **Honest health checks.** An orphaned agent answers `/api/health` even when no
  helper owns it, so a bare probe can report success on a broken install. Startup
  only counts when the helper is alive, the API returns 200, and no agent has been
  reparented to `launchd`.

| Env | Purpose |
|-----|---------|
| `STOP_ONLY=1` | Stop everything and exit |
| `SKIP_BUILD=1` | Relaunch the installed app without rebuilding |
| `PORT=8787` | API port to free and probe |
| `TIMEOUT=90` | Seconds to wait for the supervised chain |

`CONFIG` and `SKIP_TAURI` are forwarded to `package-macos-dmg.sh`.

## Signing / notarization

The script ad-hoc signs for local use. For distribution, replace with Developer ID
signing + `notarytool` / `stapler` after the assemble step.
