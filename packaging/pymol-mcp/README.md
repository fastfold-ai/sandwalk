# Sandwalk PyMOL MCP plugin packaging

Plugin Manager zip for a live PyMOL MCP bridge. Works with **commercial and
open-source** PyMOL (Plugin Manager → Install from URL).

The MCP stdio server (`agentic-pymol`) is **vendored** under
`vendor/agentic-pymol/` (mirrored from
`cli/src/agent/mcps/pymol_mcp/vendor/agentic-pymol/`). Installs use that local
path — no GitHub fetch at setup time.

Current version: see [`VERSION`](VERSION) (currently **v0.0.1**).

Managed launcher helpers live in the CLI at `cli/src/agent/mcps/pymol_mcp/`.

## Layout

```
packaging/pymol-mcp/
  sandwalk_pymol_plugin/   # PyMOL Plugin Manager package (UI + TCP)
  vendor/agentic-pymol/    # Installable MCP server (bundled into the zip)
  scripts/build_plugin_zip.sh
```

CLI source of truth for the server package (ships with sandwalk wheel):

```
cli/src/agent/mcps/pymol_mcp/vendor/agentic-pymol/
```

## Build

```bash
./scripts/build_plugin_zip.sh
# optional: ./scripts/build_plugin_zip.sh v0.0.1
```

Outputs:

- `dist/sandwalk-pymol-plugin-v0.0.1.zip` (versioned)
- `dist/sandwalk-pymol-plugin.zip` (stable name)

Each zip includes `sandwalk_pymol_plugin/vendor/agentic-pymol/` so
`sandwalk-pymol setup` can `pip install` offline from the plugin tree.

## Host (manual)

Copy into sandwalk-landing and deploy:

```bash
mkdir -p ../../sandwalk-landing/public/pymol
cp dist/sandwalk-pymol-plugin.zip ../../sandwalk-landing/public/pymol/plugin.zip
cp dist/sandwalk-pymol-plugin-v0.0.1.zip ../../sandwalk-landing/public/pymol/plugin-v0.0.1.zip
```

Public URLs:

- `https://sandwalk.sh/pymol/plugin.zip` (latest)
- `https://sandwalk.sh/pymol/plugin-v0.0.1.zip` (pinned)

## After install in PyMOL

1. Plugin Manager → Install from URL → fetch the public zip
2. In the PyMOL command line: `sandwalk-pymol setup` (or `sandwalk mcp install pymol`)
3. Open the plugin → **Start Listening**
4. In Sandwalk: enable the PyMOL MCP

## Attribution

`vendor/agentic-pymol` is based on Arcadia Science’s agentic-pymol (MIT).
See `vendor/agentic-pymol/LICENSE` and `NOTICE`.
