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
cd cli && uv sync                # CLI + agent server (+ dev tools)
# cd cli && uv sync --extra all  # optional: chemistry / single-cell / ML
```

## Lint & typecheck

Prefer cohesive modules. Review unusually large files for mixed responsibilities
in PR review; do not split based only on line count.

Python (**ruff** + **mypy**):

```bash
cd cli
uv run ruff check src
uv run ruff format --check src
uv run mypy          # scoped packages in pyproject.toml; expanding over time
```

Ruff formats near `line-length = 100` and ignores `E501`.

Web:

```bash
pnpm --filter @sandwalk/agent-local-web lint:check
pnpm --filter @sandwalk/agent-local-web typecheck
pnpm --filter @sandwalk/agent-local-web build
```

Mac:

```bash
pnpm lint:mac
```

## Dev loop

```bash
scripts/dev-api.sh        # agent API from this checkout (:8787); restart after Python edits
scripts/dev-ui.sh         # Tauri window + Vite (:1420) with HMR; `scripts/dev-ui.sh web` for browser only
scripts/stop-packaged-app.sh   # if the installed Sandwalk.app / menubar server holds :8787
```

## Tests

```bash
scripts/verify.sh         # same gate as CI: web typecheck/lint/build/coverage + cli ruff/mypy/pytest
scripts/verify.sh web     # or: cli | e2e
pnpm e2e                  # Playwright: split grid + terminals (needs the API running)
pnpm e2e:bench            # perf benchmarks; compare runs with `pnpm e2e:compare a.json b.json`
# macOS only:
pnpm test:mac
```

See [.github/TESTING.md](.github/TESTING.md) for coverage gates, the e2e/perf
harness, and the live multi-agent bench. The same workflow is packaged for
coding agents in [AGENTS.md](AGENTS.md) and `.agents/skills/`.

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
