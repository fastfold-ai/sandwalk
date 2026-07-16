# sandwalk docs (`@sandwalk/docs`)

Hosted documentation site for sandwalk — [Fumadocs](https://fumadocs.dev) + Next.js, same stack as [fastfold-docs](https://github.com/fastfold-ai/fastfold-docs).

Lives at the repo-root `docs/` package (not under `apps/`), so Vercel can point at this directory the same way as the Fastfold Cloud docs repo.

## Develop

From the monorepo root:

```bash
pnpm install
pnpm dev:docs
```

Or from this package:

```bash
cd docs
pnpm install
pnpm dev
```

Open [http://localhost:3001](http://localhost:3001).

## Content

MDX lives in [`content/`](./content/). Sidebar order is [`content/meta.json`](./content/meta.json).

## Deploy

Point Vercel (or equivalent) at this directory as the project root:

| Setting | Value |
|---------|--------|
| Root Directory | `docs` |
| Install | `pnpm install` from monorepo root (workspace) |
| Build | `pnpm build` (in `docs/`) or `pnpm build:docs` from root |
| Output | Next.js default |

Set `NEXT_PUBLIC_SITE_URL` to the production docs URL when available.

Contributor / CI testing notes: [`.github/TESTING.md`](../.github/TESTING.md) (not part of this site).
