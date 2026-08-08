# RayMol MCP

Connect Sandwalk agents to a **live RayMol** session (Metal PyMOL for Apple
Silicon) via RayMol’s built-in MCP bridge.

## Architecture

```
Sandwalk agent  --stdio-->  RayMol --mcp-bridge
                              --HTTP + token-->  RayMol app MCP (127.0.0.1)
```

RayMol owns the MCP server inside the app. Sandwalk spawns
`RayMol --mcp-bridge` (same path as Claude Desktop). When MCP is enabled,
RayMol writes `~/Library/Application Support/RayMol/mcp.json` (port + token)
for the bridge to use.

## Setup

1. **Install RayMol** from [https://raymol.io/](https://raymol.io/)

   - Direct notarized DMG, or
   - Homebrew: `brew install --cask javierbq/raymol/raymol`

   Use the **direct-download / Homebrew** builds. Mac App Store builds omit MCP
   (App Store sandboxing).

   **Drag RayMol.app to `/Applications`.** Sandwalk can find and use RayMol while
   it runs straight from the mounted DMG, but that path disappears on eject and
   the bridge breaks. Install and doctor warn when RayMol is on a mounted volume.

2. **Enable MCP in RayMol**  
   Open RayMol → toolbar **RayMol MCP** → toggle **Enable MCP server**.

3. **Allow MCP access**  
   Once MCP is on, RayMol prompts to **Allow** when a client connects.
   Click **Allow** — otherwise the connection will not establish and tools
   will fail.

4. **Connect Sandwalk** (one-time)

   ```bash
   sandwalk mcp install raymol
   ```

   Or use **Install** on the RayMol MCP detail page in the dashboard.
   Approve the Allow prompt in RayMol if it appears.

5. **Enable** the RayMol MCP in Sandwalk (toggle). Keep RayMol open with MCP
   enabled (and access Allowed) while the agent runs.

## How Sandwalk finds RayMol

In order, first match wins, and every candidate must exist on disk:

1. `mcp.raymol_binary` in config (written by Install; ignored when stale)
2. A **running** RayMol, read from the process table — covers a DMG or any
   non-standard location, which Spotlight does not index
3. `RayMol` on `PATH`
4. App bundles: `/Applications`, `~/Applications`, Spotlight (bundle id then
   name), Homebrew Caskroom, and `/Volumes/*/RayMol.app`

A copy under `/Volumes` is only used as a last resort, so a real install in
`/Applications` always wins even while the DMG copy is the one running.

## Doctor

```bash
sandwalk mcp doctor raymol
```

Checks: RayMol binary present, MCP handoff file (`mcp.json`), and a live probe.

## Troubleshooting

**App not found** — Install from raymol.io (DMG/Homebrew), not the Mac App Store.

**`No such file or directory: '/Applications/RayMol.app/...'`** — Sandwalk had a
path for RayMol that no longer exists. Usually RayMol was run from the DMG (then
ejected), moved, or deleted. Reopen RayMol from `/Applications` and re-run
Install; Sandwalk clears the stale path automatically.

**Probe fails / no tools** — Enable MCP in the RayMol toolbar first so
`~/Library/Application Support/RayMol/mcp.json` exists, then click **Allow**
when RayMol asks to grant MCP access.

**"handoff found but the RayMol app is missing"** — `mcp.json` outlives the app
that wrote it. RayMol is not running from the recorded location; reopen it (from
`/Applications`) and re-run Install.

**Mac App Store** — Same app without MCP. Switch to the direct or Homebrew build
for AI control.
