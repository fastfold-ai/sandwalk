---
name: sites-hosting
description: Securely package and publish a validated static dist directory to Sandwalk Sites, then wait for a ready public URL.
author: sandwalk
category: Built-in
version: 1.0.0
---

# Sites Hosting

Publish the exact static output produced by `sites-building`. Use this skill when
the user asks to host, deploy, publish, or update a Sandwalk Site.

## Requirements

- Publish static output only. The input must be the final validated `dist/`, not
  source files, a project root, or a development server.
- `FASTFOLD_API_KEY` is required. Prefer the existing environment or Sandwalk
  Integrations credential. If `sites.manage` reports missing authentication, ask
  the user to configure it; never request, print, or inspect the secret value.
- Use `sites.manage` for all local registration and remote publication operations. Read its current
  action and argument descriptions before each workflow; they are authoritative.
  Do not invent actions, fields, provider APIs, or direct HTTP requests.

## Workflow

1. **Identify the exact output.** Resolve the intended `dist/`. For a changed
   existing site, retain the site identifier returned by `sites.manage`; do not
   silently create a second site.
2. **Package and validate.** Run from this skill's directory:

   ```bash
   python scripts/package_site.py <project>/dist <workspace>/site.zip
   ```

   The script emits one JSON object on stdout. It creates a deterministic archive
   and adjacent manifest, then verifies that both describe exactly the same files.
   Fix every failure; never bypass path, secret, file-count, or 100 MB limits.
   Read [Package contract](references/package-contract.md) when diagnosing a failure.
3. **Choose the address.** Ask for a custom slug only when the user cares about
   the address. Otherwise allow Sites to generate one. A generated slug, or a
   requested custom slug when available, is served at
   `https://<slug>.sandwalk.site`. A requested slug is not reserved until the tool
   confirms it.
4. **Register or update.** Call `sites.manage` with `action="create"` and the
   validated `dist/` path once, or `action="update"` with the retained local site
   identifier after rebuilding. The tool snapshots and independently validates
   the exact directory.
5. **Publish.** After confirming this public side effect with the user, call
   `sites.manage(action="publish", site_id="<id>")`. Pass `slug` only when the
   user requested one. The tool packages, uploads, and waits for the deployment.
6. **Confirm the result.** `sites.manage(action="publish")` waits for the remote
   deployment to reach a terminal result. Report success only when that call returns
   a site with `status="published"` and the service-provided URL. The `status` action
   reads the last confirmed local state; it does not resume a timed-out remote poll.
   On timeout or an unknown result, report that publication is unconfirmed, include
   the local site identifier, and do not republish automatically. Read
   [Publishing lifecycle](references/publishing-lifecycle.md) for communication rules.

## Completion Rules

- Never say deployed, published, live, successful, or ready before status is
  exactly the tool's ready/success terminal state.
- A URL in an accepted or processing response is provisional, not proof of
  success.
- On success, state the final URL and whether the slug was generated or custom.
- On non-ready outcomes, state the observed status, concise reason, and next safe
  action. Never fabricate a URL from a requested slug.
- Keep progress messages factual: packaging, upload accepted, processing, ready,
  or failed. Do not expose credentials, raw authorization errors, or provider
  implementation details.

## Resources

- [Package contract](references/package-contract.md)
- [Publishing lifecycle](references/publishing-lifecycle.md)
- `scripts/package_site.py` — deterministic package, manifest, and exact-output validation
