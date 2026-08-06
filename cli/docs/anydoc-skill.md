# anydoc skill (convert-documents-to-markdown)

Firecrawl’s [anydoc](https://github.com/firecrawl/anydoc) skill converts Word,
PowerPoint, Excel, OpenDocument, RTF, EPUB, CSV, and PDF files to Markdown.

## Install the skill

```bash
sandwalk skills add firecrawl/anydoc
```

## Runtime dependencies

anydoc needs Node.js 20+ and the `@firecrawl/anydoc` CLI. Sandwalk manages a
local install under `$SANDWALK_CONFIG_DIR/skill-deps/anydoc/`.

```bash
sandwalk skills deps status convert-documents-to-markdown
sandwalk skills deps install convert-documents-to-markdown
sandwalk skills deps reinstall convert-documents-to-markdown
sandwalk skills deps doctor convert-documents-to-markdown
```

Web UI: open the skill detail page for **Install dependencies** / **Reinstall**
/ **Run health check**.

## Agent usage

Prefer the managed binary when present; otherwise:

```bash
npx -y @firecrawl/anydoc <file>
npx -y @firecrawl/anydoc <file> -o out.md
```

Scanned / image-only PDFs need OCR (hosted Firecrawl Parse); local anydoc does
not OCR.
