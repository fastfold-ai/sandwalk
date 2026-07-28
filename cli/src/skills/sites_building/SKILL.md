---
name: sites-building
description: Build, preview, validate, and prepare static websites, HTML reports, dashboards, landing pages, and Vite/React sites for Sandwalk Sites hosting.
author: sandwalk
category: Built-in
version: 1.0.0
---

# Sites Building

Create a complete static site, validate its deployable `dist/`, preview it locally,
register it with Sites when the tool supports registration, then hand off to
`sites-hosting` unless the user explicitly requests local-only work.

## Scope

- Static files only: HTML, CSS, client-side JavaScript, images, fonts, and other
  browser assets.
- No server functions, databases, private runtime secrets, or server-side rendering.
- Use the lightweight static starter by default. Use Vite/React only when components
  or substantial client interaction justify a build tool.
- Preserve an existing site's framework, lockfile, scripts, and structure.

## Workflow

1. **Clarify only material gaps.** Ask at most three grouped questions when missing
   content, audience, or required behavior would materially change the result.
2. **Initialize a new site.** Run one initializer from an empty target:

   ```bash
   python scripts/init_site.py <target> --template static
   python scripts/init_site.py <target> --template vite-react
   ```

3. **Bring attachments local.** Copy every user-referenced local attachment needed
   by the site; do not link to temporary session paths:

   ```bash
   python scripts/copy_attachments.py <project> <file> [<file> ...]
   ```

   Use the returned relative paths in HTML/JS. Preserve attribution when required.
4. **Author the site.** Read [Site authoring](references/site-authoring.md) for
   visualizations, math, tables, images, responsive behavior, and accessibility.
   Prefer concrete content and fit-for-purpose interactions over generic dashboard
   chrome. Do not add remote dependencies when a local implementation is sufficient.
5. **Build.**

   ```bash
   python scripts/build_site.py <project>
   ```

   The static starter copies `src/` to a clean `dist/`; Vite/React installs missing
   dependencies and runs its declared build.
6. **Validate the exact output.**

   ```bash
   python scripts/validate_site.py <project>/dist
   ```

   Fix every failure. `dist/index.html` is mandatory. Local asset references must be
   relative, remain inside `dist/`, and resolve to files. Never publish source files
   in place of the validated build.
7. **Preview locally.** From the project directory, run:

   ```bash
   python -m http.server 4173 --directory dist
   ```

   Share `http://127.0.0.1:4173/` as the local preview. Keep the server alive only
   while useful; browser automation or visual QA is optional unless requested.
8. **Register or refresh the local site.** Use only the arguments advertised by
   `sites.manage`; its tool description is the source of truth. The lifecycle is:

   ```
   sites.manage(action="create", name="<site name>", path="<project>/dist")
   sites.manage(action="update", site_id="<returned id>", path="<project>/dist")
   sites.manage(action="preview", site_id="<returned id>")
   ```

   Use `create` once and retain its returned `site_id`. After later edits, rebuild
   and validate, then use `update` with that same ID. Use `preview` only after the
   registered content is current; share its returned temporary URL and expiry.
   These actions manage a local site snapshot and preview, not durable publication.
9. **Hand off.** Unless the user requested local-only work, invoke the
   `sites-hosting` workflow with the unchanged validated `dist/`. Return a public URL
   only after hosting reports durable success.

## Quality Gates

- Every page has a unique title, useful description, semantic landmarks, logical
  heading order, visible keyboard focus, and descriptive link/button text.
- Interactive controls work by keyboard and have accessible names and states.
- Color is not the only signal; text contrast is sufficient; motion respects
  `prefers-reduced-motion`.
- Images have meaningful `alt` text (or empty `alt` when decorative), explicit
  dimensions when known, and responsive sizing.
- Tables remain usable on narrow screens. Charts include a text summary or data table.
- No absolute local paths, parent traversal, missing assets, or embedded secrets.

## Resources

- [Site authoring](references/site-authoring.md)
- `templates/static/` — no-dependency HTML/CSS starter
- `templates/vite-react/` — minimal Vite/React starter
- `scripts/init_site.py` — initialize either starter
- `scripts/copy_attachments.py` — copy local attachments into site assets
- `scripts/build_site.py` — produce a clean `dist/`
- `scripts/validate_site.py` — validate entry point and local references
