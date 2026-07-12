# MCP defaults catalog

Shortlist: four hosted MCP servers. Per-server URL, auth, signup, and config sketches.

---

## 1. Tamarind Bio

| Field | Value |
|-------|-------|
| **ID** | `tamarind` |
| **MCP URL** | `https://mcp.tamarind.bio/mcp` |
| **Transport** | Streamable HTTP |
| **Docs** | https://app.tamarind.bio/api-docs/mcp-server |
| **What it does** | Protein design, structure prediction, docking, and molecular dynamics |

### Auth

| Mode | Details |
|------|---------|
| **API key** | Header `x-api-key: <TAMARIND_API_KEY>` |

Notes:
- FastFold Connect uses **API key only** (no OAuth client registration with Tamarind).
- Get the key from the Tamarind **API Key** page (not an OAuth client secret).

### Config sketch

```json
{
  "mcpServers": {
    "tamarind": {
      "url": "https://mcp.tamarind.bio/mcp",
      "headers": { "x-api-key": "${TAMARIND_API_KEY}" }
    }
  }
}
```

---

## 2. Latch Bio

| Field | Value |
|-------|-------|
| **ID** | `latch` |
| **MCP URL** | `https://mcp.latch.bio/mcp` |
| **Transport** | Remote HTTP MCP |
| **Docs** | https://wiki.latch.bio/agent/latch-mcp |
| **What it does** | Bioinformatics workflows, data, and compute on the Latch platform |

### Auth

| Mode | Details |
|------|---------|
| **OAuth** | Browser Connect from Dashboard → MCP or `fastfold mcp connect latch` |

---

## 3. Neurosnap

| Field | Value |
|-------|-------|
| **ID** | `neurosnap` |
| **MCP URL** | `https://neurosnap.ai/mcp` |
| **Transport** | Streamable HTTP |
| **Docs** | https://neurosnap.ai/overview?view=api |
| **What it does** | Protein folding, docking, design, and computational biology jobs |

### Auth

| Mode | Details |
|------|---------|
| **API key** | `Authorization: Bearer <NEUROSNAP_API_KEY>` (also accepts `X-API-KEY`) |

---

## 4. Linear

| Field | Value |
|-------|-------|
| **ID** | `linear` |
| **MCP URL** | `https://mcp.linear.app/mcp` |
| **Transport** | Streamable HTTP |
| **Docs** | https://linear.app/docs/mcp |
| **What it does** | Issues, projects, and comments for product and ops workflows |

### Auth

| Mode | Details |
|------|---------|
| **OAuth** | Preferred for interactive Connect |
| **API key** | `Authorization: Bearer <LINEAR_API_KEY>` |

---

## Auth summary

| ID | Suggested `auth` |
|----|------------------|
| tamarind | `api_key` (`x-api-key`, `TAMARIND_API_KEY`) |
| latch | `oauth` |
| neurosnap | `api_key` (`Authorization: Bearer`, `NEUROSNAP_API_KEY`) |
| linear | `api_key_or_oauth` (`Authorization: Bearer`, `LINEAR_API_KEY`) |
