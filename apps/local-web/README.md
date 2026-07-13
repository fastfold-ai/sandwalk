# local-web

React dashboard for the local Sandwalk / FastFold agent server.

```bash
# from monorepo root
pnpm install
pnpm dev
```

Opens http://127.0.0.1:8969 and expects the agent API on http://127.0.0.1:8787.

## Tests & coverage

```bash
pnpm test                 # from monorepo root
pnpm test:coverage        # Vitest + ≥80% on included modules; writes coverage/lcov.info
```

Codecov flag: `local-web`. See [docs/TESTING.md](../../docs/TESTING.md).
