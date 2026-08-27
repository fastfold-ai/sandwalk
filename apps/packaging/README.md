# Sandwalk macOS packaging

Builds a single installable DMG:

```text
Sandwalk.app                                 ← Tauri client (what users open)
└── Contents/Helpers/Sandwalk Server.app     ← menubar supervisor (no Dock icon)
    └── Contents/Resources/
        ├── agent-runtime/                   ← CPython + sandwalk (serve)
        └── ui-dist/                         ← Vite dashboard for API hosting
```

On first helper launch (when `agent-runtime` is present), the app installs a
**managed** `~/.local/bin/sandwalk` shim that runs the bundled CLI
(`python -m cli`). It refreshes that shim on later launches (app moves/updates)
and never overwrites a foreign curl/uv/pipx install unless the user clicks
**Reinstall** in General settings. If needed, it appends `~/.local/bin` to
`PATH` in `~/.zprofile`.

**Desktop updates include the CLI runtime.** The updater archive is the full
nested `Sandwalk.app` (UI + helper + `agent-runtime`). Applying an in-app
update replaces the bundled server/CLI; the helper rewrites the PATH shim to
the new runtime on next launch.

## Prerequisites

- Full **Xcode** (Swift helper) and Rust (Tauri client)
- **`cmake`** — `brew install cmake`. Required by `whisper-rs-sys`, which builds
  whisper.cpp for the STT crate; without it the Tauri build fails with
  ``is `cmake` not installed?``
- **`uv`** — used to copy a managed CPython and `pip install` the agent CLI into
  the helper (`apps/packaging/bundle-agent-runtime.sh`)
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
- `Sandwalk-macos-arm64.dmg` (stable alias for `/releases/latest/download/…`)
- `stage/Sandwalk.app` (assembled app before DMG)
- `agent-runtime/` (staging copy of the embedded Python)

Install for local QA:

```bash
INSTALL=1 ./apps/packaging/package-macos-dmg.sh
```

Reuse an existing Tauri bundle (faster iteration on nesting):

```bash
SKIP_TAURI=1 ./apps/packaging/package-macos-dmg.sh
```

Skip embedding the Agent Server runtime (dev only — needs a checkout/`uv` host):

```bash
SKIP_AGENT_RUNTIME=1 ./apps/packaging/package-macos-dmg.sh
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

## Updater artifacts

After assembling the nested app, the packager also builds:

- `Sandwalk.app.tar.gz` — full nested app for `tauri-plugin-updater`
- `Sandwalk.app.tar.gz.sig` — minisign signature (when `TAURI_SIGNING_PRIVATE_KEY` /
  `TAURI_SIGNING_PRIVATE_KEY_PATH` is set, typically `apps/local-web/src-tauri/.updater-key`)
- `latest.json` — GitHub Releases updater manifest

Upload those (plus the DMG) to the GitHub Release. The desktop app checks
`…/releases/latest/download/latest.json`.

Generate a keypair once (do not commit the private key):

```bash
cd apps/local-web
pnpm exec tauri signer generate --ci -p "" -w src-tauri/.updater-key
# Put the .pub contents into src-tauri/tauri.conf.json → plugins.updater.pubkey
```

## Signing

| Layer | What |
|-------|------|
| **Apple codesign** | First **Developer ID Application** identity in the keychain, or `CODESIGN_IDENTITY`. Falls back to ad-hoc (`-`). |
| **Notarization** | When `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, and `APPLE_TEAM_ID` are set, the DMG is submitted and stapled. |
| **Updater (minisign)** | `TAURI_SIGNING_PRIVATE_KEY` (local `.updater-key` or CI secret). Unrelated to Apple. |

```bash
# Uses Developer ID from Keychain when present
./apps/packaging/package-macos-dmg.sh

# Force ad-hoc
CODESIGN_IDENTITY=- ./apps/packaging/package-macos-dmg.sh
```

Step-by-step certificate, local QA, `.p12` export, and GitHub secrets:
[APPLE-SIGNING.md](./APPLE-SIGNING.md).

CI: [`.github/workflows/release-desktop.yml`](../../.github/workflows/release-desktop.yml)
(`workflow_dispatch` → signed DMG + updater artifacts → GitHub Release).

**Repo secrets:**

| Secret | Value |
|--------|--------|
| `TAURI_SIGNING_PRIVATE_KEY` | Full contents of `apps/local-web/src-tauri/.updater-key` |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Empty if the key was generated with `-p ""` |
| `RELEASE_GITHUB_TOKEN` | Optional classic PAT (`repo` scope) so the GitHub Release is attributed to you, not `github-actions`. |
| `APPLE_CERTIFICATE` | Base64 of the Developer ID `.p12` |
| `APPLE_CERTIFICATE_PASSWORD` | `.p12` password |
| `APPLE_SIGNING_IDENTITY` | `Developer ID Application: Fastfold AI Labs, Corp (SG5Y53G9MJ)` |
| `APPLE_ID` | Apple ID email |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password |
| `APPLE_TEAM_ID` | `SG5Y53G9MJ` |

Do **not** commit the updater private key or the `.p12`. The minisign public key already
lives in `apps/local-web/src-tauri/tauri.conf.json` → `plugins.updater.pubkey`.
