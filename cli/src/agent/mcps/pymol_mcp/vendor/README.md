# Vendored PyMOL MCP server

`agentic-pymol/` is an installable copy of the Arcadia agentic-pymol MCP
server (MIT), maintained in-tree for Sandwalk.

- Installed into `~/.sandwalk/pymol-mcp/venv` by `sandwalk mcp install pymol`
- Mirrored under `packaging/pymol-mcp/vendor/` for the Plugin Manager zip
- No runtime `git+https://…` dependency

Edit here, then sync packaging (or rebuild the zip — the build script copies
from this tree when packaging/vendor is missing).
