# CLI functional integration suite

Real-process tests for the `sandwalk` CLI under an **isolated temporary HOME**.

## Commands (do not mix these up)

| Command | What runs | Approx size |
|---------|-----------|-------------|
| `pnpm test:cli:functional` | Offline real-process **smoke** | ~10–20 tests, ~10s |
| `pnpm test:cli:all` | Functional + network + live chat | minutes |
| `pnpm test:cli:unit` | Full mocked **unit** suite (not smoke) | ~2400 tests, several minutes |
| `pnpm test:cli` | CI mix: unit + offline functional | same as unit + a bit |

```bash
pnpm test:cli:functional   # quick smoke — start here
pnpm test:cli:all          # full CLI integration (uses ~/.sandwalk keys)
pnpm test:cli:unit         # full unit suite — expect several minutes
```

Opt-in lanes (`cli_network`, `cli_e2e`, Modal, …) are auto-deselected unless their env gate is set — no long `-m "not …"` needed.

Case catalog: [CASES.md](CASES.md).
