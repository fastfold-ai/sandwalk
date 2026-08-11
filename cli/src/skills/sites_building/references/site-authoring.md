# Site authoring

Use only the capabilities the content needs. A clear static page is better than a
large client bundle.

## Report shell

For reports, briefs, analyses, and dashboards, start from the bundled report shell
instead of inventing a visual theme. The shell is enforced at build/validate time:

- **Do not reinvent** the theme control, TOC chrome, layout grid, or Sandwalk
  footer. Keep the HTML comments
  `<!-- sandwalk:shell:actions -->` … `<!-- /sandwalk:shell:actions -->` and
  `<!-- sandwalk:shell:footer -->` … `<!-- /sandwalk:shell:footer -->`.
  `build_site.py` restores those blocks and overwrites `shell.css` every build.
- **Edit only** section content inside `<main>`, TOC link targets/labels inside
  `nav.toc`, report kind text, title/lede, and optional component markup. Prefer
  starter classes over new CSS; do not replace `shell.css` or restyle
  `.report-actions`, `.report-layout`, `.toc`, or `.sandwalk-logo`.
- Use a neutral white/zinc light theme and near-black/zinc dark theme. Accent colors
  should communicate meaning; do not tint the entire report green, blue, or purple.
- Keep the top metadata line in `KIND • <time class="report-date" …>` form. Leave
  `__SANDWALK_REPORT_DATE__` in the `<time>` `datetime` and text; `build_site.py`
  replaces it with UTC today’s ISO date. Do not invent a calendar date in that
  slot (historical years in charts/tables are fine).
- Keep `nav.toc` with class `toc`, title `toc-title`, and `#section` links that match
  your section ids. Do not rename it to “On this page” with a custom layout.
- Keep the theme-aware scrollbar and full-viewport `html`/`body` background so dark
  reports do not show a white gutter beside the scrollbar.
- Use at least three content-appropriate interactive capabilities for a rich report:
  interactive plots, sortable/filterable tables, tabs, code copy, Mermaid, KaTeX,
  collapsibles, or search. Do not include empty showcase widgets.

### Reusable report components

The static starter already styles the common report vocabulary. Reuse these classes
instead of reading or rewriting `styles.css`: `callout-banner`, `stat-grid`, `card`,
`chart-card`, `chart-frame`, `diagram-card`, `mermaid`, `math-block`, `math-legend`,
`tabs`, `tab-panel`, `tab-heading`, `filter`, `table-wrap`, `code-block`,
`copy-button`, `fit-grid`, `fit-card`, `fit-label`, `fit-good`, `fit-caution`,
`fit-poor`, and `sources-list`. Only inspect or change CSS when the requested design
cannot be expressed with those components.

## Diagrams and math

- Mermaid is appropriate for flows, architectures, timelines, and state diagrams.
  Pin a browser-compatible version, render into a labeled figure, and include a
  nearby prose explanation. Treat diagram text as untrusted input and use Mermaid's
  strict security mode. For Sandwalk previews, use a pinned classic browser bundle
  such as `mermaid.min.js` or vendor it locally. Do not import Mermaid from an HTTPS
  URL inside `<script type="module">`; WebKit can enter a module-loader microtask
  loop after iframe refresh and consume an entire CPU core.
- KaTeX is appropriate for equations. Pin its CSS and JavaScript versions and
  preserve a readable text or TeX fallback. Use Subresource Integrity only after
  verifying the hash against the exact fetched asset; never invent or copy a hash
  from another version. Explain symbols when they first appear.
- If network-independent viewing matters, download permitted library assets into the
  project instead of relying on a CDN.

## Plots and charts

- Use a chart only when it communicates a relationship better than prose or a small
  table. Prefer Plotly, Chart.js, or lightweight native SVG/canvas code according to
  the task; pin any third-party version.
- Make charts responsive, label axes and units, avoid misleading truncated scales,
  and use palettes that remain distinguishable with common color-vision deficiencies.
- Add a concise textual takeaway and expose the underlying values in an accessible
  table or downloadable local file.

## Tables

- Use `caption`, `thead`, and scoped header cells. State units in headers.
- For wide tables, place the table in a keyboard-accessible horizontal overflow
  region with a visible label. Do not shrink text until it becomes unreadable.
- Add sorting/filtering only when it helps; controls need labels and must preserve
  header associations. On small screens, prefer scrolling over dropping data.
- Code samples use a readable high-contrast theme and include a keyboard-accessible
  copy button when copying is a likely reader action.

## Images and attachments

- Copy referenced attachments with `scripts/copy_attachments.py`; never point a
  published page at an absolute filesystem path or temporary upload URL.
- Use modern, compressed formats when practical without degrading scientific figures.
  Preserve originals when fidelity or provenance matters.
- Give informative images concise alt text that conveys their purpose. For complex
  figures, add a caption and longer adjacent explanation. Decorative images use
  `alt=""`.
- Set `width` and `height` to reduce layout shift and use
  `max-width: 100%; height: auto` for responsiveness.

## Responsive and accessible interaction

- Start with a single-column small-screen layout, then add columns when space allows.
  Test likely breakpoints around 375, 768, and 1280 CSS pixels.
- Use semantic HTML before ARIA. Keep DOM order aligned with reading and tab order.
- All functionality must be available without a mouse. Do not remove focus outlines.
- Associate labels and errors with form controls. Announce meaningful asynchronous
  updates with a restrained live region.
- Respect reduced motion and system color preferences.

## Static-site safety

- Do not put API keys or private data in HTML, JavaScript, source maps, or assets.
- Avoid `innerHTML` for untrusted content. If rich user content is unavoidable,
  sanitize it with a maintained client-side library.
- Prefer relative links so the same `dist/` works in local preview and hosting.
- Keep all required local resources inside `dist/`; validation intentionally rejects
  root-relative and parent-traversing asset paths.
