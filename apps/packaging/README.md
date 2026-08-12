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

## Signing (today vs Apple later)

### Today — self-sign (default)

| Layer | What |
|-------|------|
| **Apple codesign** | Ad-hoc (`CODESIGN_IDENTITY=-`). Users may need right-click → Open once. |
| **Updater (minisign)** | Automated via `TAURI_SIGNING_PRIVATE_KEY` (local `.updater-key` or CI secret). |

```bash
# Local package (ad-hoc Apple + auto minisign if key file exists)
./apps/packaging/package-macos-dmg.sh

# Explicit identity (still ad-hoc unless you pass a real Developer ID name)
CODESIGN_IDENTITY=- ./apps/packaging/package-macos-dmg.sh
```

CI: [`.github/workflows/release-desktop.yml`](../../.github/workflows/release-desktop.yml)  
(`workflow_dispatch` → builds DMG + updater artifacts → GitHub Release).

**Repo secrets:**

| Secret | Value |
|--------|--------|
| `TAURI_SIGNING_PRIVATE_KEY` | Full contents of `apps/local-web/src-tauri/.updater-key` |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Empty if the key was generated with `-p ""` |
| `RELEASE_GITHUB_TOKEN` | Optional classic PAT (`repo` scope) so the GitHub Release is attributed to you, not `github-actions`. |

Do **not** commit the private key. The public key already lives in
`apps/local-web/src-tauri/tauri.conf.json` → `plugins.updater.pubkey`.

### Later — Apple Developer ID + notarization

When the Apple Developer Program membership is active:

1. Create a **Developer ID Application** certificate in Apple Developer → Certificates.
2. Export it as a `.p12` and add CI secrets (typical names):

| Secret | Purpose |
|--------|---------|
| `APPLE_CERTIFICATE` | Base64 of the `.p12` |
| `APPLE_CERTIFICATE_PASSWORD` | `.p12` password |
| `APPLE_ID` | Apple ID email |
| `APPLE_APP_SPECIFIC_PASSWORD` | App-specific password |
| `APPLE_TEAM_ID` | 10-character Team ID |

3. In the release workflow / package step, set:

```bash
CODESIGN_IDENTITY="Developer ID Application: Fastfold AI Labs (TEAMID)"
```

4. After assemble + codesign, notarize and staple (outline for when ready):

```bash
# Submit DMG (or .app.zip) to Apple
xcrun notarytool submit apps/packaging/dist/Sandwalk-*-macos-arm64.dmg \
  --apple-id "$APPLE_ID" \
  --password "$APPLE_APP_SPECIFIC_PASSWORD" \
  --team-id "$APPLE_TEAM_ID" \
  --wait

# Staple ticket onto the DMG
xcrun stapler staple apps/packaging/dist/Sandwalk-*-macos-arm64.dmg
```

5. Keep **minisign** updater signing as-is — Apple notarization does not replace it.
   Notarization satisfies Gatekeeper; minisign authenticates the Tauri update channel.

Until then, ship draft/pre-releases with ad-hoc codesign and document “right-click → Open”
for dogfood installs.
