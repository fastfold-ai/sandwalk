# Cloud MCP defaults registry

Suggested MCP servers shipped in the Sandwalk dashboard (`/dashboard/mcp`) and CLI.

Remote defaults are **off** until Connect succeeds. Credentials are stored in `~/.sandwalk/config.json` (same store as Integrations / `sandwalk keys`).

Local stdio:

- **PyMOL** — managed launcher under `~/.sandwalk/pymol-mcp/` — see [pymol-mcp.md](../pymol-mcp.md).
- **RayMol** — `RayMol --mcp-bridge` to the app’s built-in MCP — see [raymol-mcp.md](../raymol-mcp.md).

Runtime uses [`langchain-mcp-adapters`](https://docs.langchain.com/oss/python/langchain/mcp) `MultiServerMCPClient` (stdio / SSE / streamable HTTP + auth headers).

## Shortlist

| ID | Name | Endpoint | Auth |
|----|------|----------|------|
| `pymol` | PyMOL | local stdio (`~/.sandwalk/pymol-mcp/bin/agentic-pymol`) | auto token |
| `raymol` | RayMol | local stdio (`RayMol --mcp-bridge`) | app token |
| `tamarind` | Tamarind Bio | `https://mcp.tamarind.bio/mcp` | `x-api-key` |
| `latch` | Latch Bio | `https://mcp.latch.bio/mcp` | OAuth |
| `neurosnap` | Neurosnap | `https://neurosnap.ai/mcp` | Bearer / `X-API-KEY` |
| `linear` | Linear | `https://mcp.linear.app/mcp` | OAuth preferred **or** Bearer |

## CLI

```bash
sandwalk mcp                 # status (catalog + registered)
sandwalk mcp list
sandwalk mcp catalog
sandwalk mcp install pymol   # managed local launcher + enable
sandwalk mcp install raymol  # resolve RayMol app + enable
sandwalk mcp doctor pymol
sandwalk mcp doctor raymol
sandwalk mcp connect neurosnap --api-key "$NEUROSNAP_API_KEY"
sandwalk mcp validate neurosnap
sandwalk mcp enable|disable <id>
sandwalk mcp add my-server --url https://example.com/mcp
sandwalk mcp remove my-server
```

Interactive session: `/mcp` (same actions).

## Product wiring

- Catalog: `src/agent/mcp_catalog.py`
- Connect / OAuth / probe: `src/agent_server/mcp_service.py`
- CLI helpers: `src/agent/mcp_manage.py`
- API: `GET /v1/mcp-servers/catalog`, connect/validate/enable, OAuth callback
- Runtime headers for enabled catalog MCPs
- Custom remotes: static headers (config secrets) + optional headers-helper command; OAuth fields stored for later Connect
- Doctor category `mcp` (live probe); dashboard catalog uses cached health for fast load

See [catalog.md](catalog.md) for per-server details.
