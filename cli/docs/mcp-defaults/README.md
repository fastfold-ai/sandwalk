# Cloud MCP defaults registry

Suggested remote MCP servers shipped in the FastFold agent dashboard (`/dashboard/mcp`) and CLI.

Defaults are **off** until Connect succeeds. Credentials are stored in `~/.fastfold-cli/config.json` (same store as Integrations / `fastfold keys`).

Runtime uses [`langchain-mcp-adapters`](https://docs.langchain.com/oss/python/langchain/mcp) `MultiServerMCPClient` (stdio / SSE / streamable HTTP + auth headers).

## Shortlist

| ID | Name | Public MCP URL | Auth |
|----|------|----------------|------|
| `tamarind` | Tamarind Bio | `https://mcp.tamarind.bio/mcp` | `x-api-key` |
| `latch` | Latch Bio | `https://mcp.latch.bio/mcp` | OAuth |
| `neurosnap` | Neurosnap | `https://neurosnap.ai/mcp` | Bearer / `X-API-KEY` |
| `linear` | Linear | `https://mcp.linear.app/mcp` | OAuth preferred **or** Bearer |

## CLI

```bash
fastfold mcp                 # status (catalog + registered)
fastfold mcp list
fastfold mcp catalog
fastfold mcp connect neurosnap --api-key "$NEUROSNAP_API_KEY"
fastfold mcp validate neurosnap
fastfold mcp enable|disable <id>
fastfold mcp add my-server --url https://example.com/mcp
fastfold mcp remove my-server
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
