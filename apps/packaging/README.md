# Sandwalk macOS packaging

Builds a single installable DMG:

```text
Sandwalk.app                                 ← Tauri client (what users open)
└── Contents/Helpers/Sandwalk Server.app     ← menubar supervisor (no Dock icon)
```

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

## Signing / notarization

The script ad-hoc signs for local use. For distribution, replace with Developer ID
signing + `notarytool` / `stapler` after the assemble step.
