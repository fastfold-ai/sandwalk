# CLI integration case catalog

Real `sandwalk` process + isolated temporary `HOME`.

**Unit tests:** `pnpm test:cli:unit` (never runs this folder)  
**CI-safe:** `pnpm test:cli` (unit + `cli_functional`)  
**Full integration:** `pnpm test:cli:all`

## Currently implemented

| Case | File | Marker | Notes |
|------|------|--------|-------|
| `--version` / `tool list` / `config` | `test_cli_smoke.py` | `cli_functional` | Always CI |
| `sandbox modal` / `builtin` | `test_cli_sandbox_config.py` | `cli_functional` | Dummy Modal tokens |
| Local `skills add` + `doctor --json` | `test_cli_skills_local.py` | `cli_functional` | Offline |
| `skills disable` / `enable` | `test_cli_skills_toggle.py` | `cli_functional` | Offline |
| Sibling `fold` checkout install | `test_cli_skills_toggle.py` | `cli_functional` | Skips if `../skills` missing |
| `mcp list` / `mcp catalog` | `test_cli_catalog.py` | `cli_functional` | No connect |
| `specialists list` | `test_cli_catalog.py` | `cli_functional` | Defaults seeded |
| `serve` + `/v1/health` | `test_cli_serve_health.py` | `cli_functional` | Spawn + poll + kill |
| Featured `fold` / `boltz` / `md` / `boltzgen` | `test_cli_skills_network.py` | `cli_network` | GitHub |
| One-shot chat / fold+chat / ops.todo tool | `test_cli_e2e_chat.py` | `cli_e2e` | Needs LLM key |

## Suggested next cases

| Case | Suggested gate |
|------|----------------|
| Fold job via FastFold Cloud API | `e2e` + `FASTFOLD_API_KEY` |
| Modal probe via CLI `sandbox probe` | existing `modal_e2e` |
| Interactive `/sandbox` via pexpect | `integration` (opt-in) |
