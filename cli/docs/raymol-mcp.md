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

## Doctor

```bash
sandwalk mcp doctor raymol
```

Checks: RayMol binary present, MCP handoff file (`mcp.json`), and a live probe.

## Troubleshooting

**App not found** — Install from raymol.io (DMG/Homebrew), not the Mac App Store.

**Probe fails / no tools** — Enable MCP in the RayMol toolbar first so
`~/Library/Application Support/RayMol/mcp.json` exists, then click **Allow**
when RayMol asks to grant MCP access.

**Mac App Store** — Same app without MCP. Switch to the direct or Homebrew build
for AI control.
