# Site authoring

Use only the capabilities the content needs. A clear static page is better than a
large client bundle.

## Diagrams and math

- Mermaid is appropriate for flows, architectures, timelines, and state diagrams.
  Pin a browser-compatible version, render into a labeled figure, and include a
  nearby prose explanation. Treat diagram text as untrusted input and use Mermaid's
  strict security mode.
- KaTeX is appropriate for equations. Pin its CSS and JavaScript versions, include
  integrity metadata when loading from a CDN, and preserve a readable text or TeX
  fallback. Explain symbols when they first appear.
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
- Respect reduced motion and system color preferences. Include print styles when the
  site is intended as a report.

## Static-site safety

- Do not put API keys or private data in HTML, JavaScript, source maps, or assets.
- Avoid `innerHTML` for untrusted content. If rich user content is unavoidable,
  sanitize it with a maintained client-side library.
- Prefer relative links so the same `dist/` works in local preview and hosting.
- Keep all required local resources inside `dist/`; validation intentionally rejects
  root-relative and parent-traversing asset paths.
