# Contributing to Sandwalk

Thanks for helping improve Sandwalk. This monorepo contains:

| Path | Package |
|------|---------|
| `cli/` | Python CLI + local agent server |
| `apps/local-web/` | Dashboard (Vite + React) |
| `apps/sandwalk-mac/` | macOS app (Swift) |

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node 22+ and [pnpm](https://pnpm.io/) 10.x
- Xcode (only for the Mac app)

## Setup

```bash
pnpm install
cd cli && uv sync --extra dev --extra all --extra api
```

## Lint & typecheck

Python (aligned with fastfold-cloud-backend: **ruff** + **mypy**):

```bash
cd cli
uv run ruff check src
uv run mypy          # scoped packages in pyproject.toml; expanding over time
```

Web:

```bash
pnpm --filter @sandwalk/agent-local-web lint:check
pnpm --filter @sandwalk/agent-local-web typecheck
pnpm --filter @sandwalk/agent-local-web build
```

## Tests

```bash
pnpm test:cli:coverage
pnpm --filter @sandwalk/agent-local-web test:coverage
# macOS only:
pnpm test:mac
```

See [docs/TESTING.md](docs/TESTING.md) for coverage gates and Codecov flags.

## Pull requests

- Keep changes focused; prefer small PRs.
- Do not commit secrets, local `.env` files, build artifacts, or large binary assets.
- Run the lint/typecheck/test commands above for the packages you touch.
- CI runs on every PR (Python lint/mypy/tests, UI lint/typecheck/build/tests, Mac tests on macOS runners).

## Configuration directory

Runtime config lives in `~/.sandwalk/`. On first import, Sandwalk copy-migrates
from legacy `~/.fastfold-cli/` (never overwrites existing files).

## License

By contributing, you agree that your contributions are licensed under the Apache License 2.0.
