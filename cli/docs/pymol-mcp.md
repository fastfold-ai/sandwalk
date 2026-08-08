# PyMOL MCP

Connect Sandwalk agents to a **live PyMOL session** (commercial or open-source)
via a Sandwalk-vendored MCP server (from Arcadia agentic-pymol, MIT).

## Architecture

```
Sandwalk agent  --stdio-->  ~/.sandwalk/pymol-mcp/bin/agentic-pymol
                              --TCP:9877 + token-->  PyMOL plugin
```

The stdio server is installed from the **local vendored package** shipped with
Sandwalk (`cli/src/agent/mcps/pymol_mcp/vendor/agentic-pymol/`). No runtime
clone from GitHub.

Credit: based on [Arcadia Science / agentic-pymol](https://github.com/Arcadia-Science/agentic-pymol)
(MIT). See `vendor/agentic-pymol/LICENSE` and `NOTICE`.

## Setup

1. **Install PyMOL** (if needed)  
   Download from [pymol.org](https://www.pymol.org/). Commercial and
   open-source builds both work.

2. **Install the PyMOL plugin**  
   In PyMOL → Plugin Manager → Install from URL →  
   `https://sandwalk.sh/pymol/plugin.zip`

3. **Install the managed launcher** (one-time)

   ```bash
   sandwalk mcp install pymol
   ```

   Reinstall / repair:

   ```bash
   sandwalk mcp install pymol --force
   ```

   Or in PyMOL: `sandwalk-pymol setup` (uses the vendor tree bundled in the zip).

4. **Start Listening** each session  
   Plugin menu → Sandwalk PyMOL MCP → Start Listening  
   (token auto-created under `~/.config/pymol-mcp/token`)

5. **Enable** the PyMOL MCP in Sandwalk (toggle or install step above).

## Doctor

```bash
sandwalk mcp doctor pymol
```

## Troubleshooting

**Ugly INFO / Rich logs dumping into the TUI** — not a session crash.
Causes: (1) FastMCP defaults to INFO + Rich→stderr at import; (2) LangChain
opens a **new** stdio session per tool call with `errlog=sys.stderr`. Fixed by
WARNING default (`PYMOL_MCP_LOG=INFO` to debug), quieter client logs, no
`slots=True` on return types, and Sandwalk permanently routing MCP child
stderr to `/dev/null` for the process. Restart the CLI; run
`sandwalk mcp install pymol --force` so the installed venv picks this up.

## Maintaining the vendored server

Edit sources under:

```
cli/src/agent/mcps/pymol_mcp/vendor/agentic-pymol/
```

Keep `packaging/pymol-mcp/vendor/agentic-pymol/` in sync (or let
`build_plugin_zip.sh` copy from the CLI vendor). Rebuild and republish the
plugin zip when shipping plugin/server changes.
