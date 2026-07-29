---
name: sites-building
description: Build, preview, validate, and prepare static websites, HTML reports, dashboards, landing pages, and Vite/React sites for Sandwalk Sites hosting.
author: sandwalk
category: Built-in
version: 1.2.1
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
- For reports, briefs, analyses, and dashboards, preserve the starter's locked report
  shell: `sandwalk:shell:*` markers, `#theme-toggle` (◐ Theme, top-right),
  `report-layout` + `nav.toc`, `shell.css`, report metadata, theme-aware scrollbar,
  and the Sandwalk SVG footer linking to https://sandwalk.sh/. Do not invent a
  different theme button, TOC layout, or text-only footer—`build_site.py` restores
  the shell markers and `shell.css`. The static starter pre-wires pinned classic
  bundles for Chart.js, highlight.js, Mermaid, and KaTeX.
- Preserve an existing site's framework, lockfile, scripts, and structure.

## Workflow

For a straightforward static report, use the fast path: initialize once, author
`src/index.html` in one pass using the starter's existing component classes, then
build, validate, and register. Do not list files after a successful initializer,
re-read copied templates in multiple chunks, inspect `styles.css`, or re-read the
generated page unless a requested design needs new CSS or validation reports an
error. Keep progress narration brief.

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
   For reports, replace every starter placeholder and set a descriptive report kind
   (for example `BRIEF • …`). Keep the `__SANDWALK_REPORT_DATE__` sentinel in the
   report meta `<time class="report-date">` — `build_site.py` stamps UTC today’s
   ISO date. Do not invent a calendar date there. Keep the Sandwalk footer SVG logo
   linking to https://sandwalk.sh/ — never replace it with plain text.
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

7. **Register or refresh the local site.** Use only the arguments advertised by
   `sites.manage`; its tool description is the source of truth. The lifecycle is:

   ```
   sites.manage(action="create", name="<site name>", path="<project>/dist")
   sites.manage(action="update", site_id="<returned id>", path="<project>/dist")
   ```

   Use `create` once and retain its returned `site_id`. After later edits, rebuild
   and validate, then use `update` with that same ID. Sandwalk automatically associates
   tool-created sites with the active session.

8. **Preview locally.** Tell the user the managed snapshot is available from the
   globe button in the session header. The sandboxed preview refreshes as registered
   content changes, so do not start a separate Vite or HTTP preview server. Call
   `sites.manage(action="preview", site_id="<returned id>")` only when the user needs
   a temporary URL outside the session panel. These actions manage a local snapshot,
   not durable publication.
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
- Reports with more than two sections have a sticky TOC with active-section feedback.
- Reports include a light/dark theme control and use at least three appropriate HTML
  strengths such as charts, sortable/filterable tables, tabs, code copy, diagrams,
  math, collapsibles, or search. Do not add interactions that do not help the content.
- The page background and themed scrollbar cover the full viewport without a white
  browser gutter in dark mode.
- Never invent a Subresource Integrity value. Verify it against the exact fetched
  asset or omit it and vendor the pinned asset locally.
- Remote ES-module imports are not allowed in deployable HTML. Use local modules or
  pinned classic browser bundles for CDN libraries; this avoids a WebKit/Tauri
  module-loader loop that can make the desktop app consume 100% CPU.
- No absolute local paths, parent traversal, missing assets, or embedded secrets.

## Resources

- [Site authoring](references/site-authoring.md)
- `templates/static/` — no-dependency HTML/CSS starter
- `templates/vite-react/` — minimal Vite/React starter
- `scripts/init_site.py` — initialize either starter
- `scripts/copy_attachments.py` — copy local attachments into site assets
- `scripts/build_site.py` — produce `dist/`, stamp report date, restore shell markers + `shell.css`
- `scripts/validate_site.py` — validate entry point, shell, references, and stamped date
- `fragments/` — locked report actions/footer/shell.css restored on every build
