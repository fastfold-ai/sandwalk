import { renderMermaidSVG } from 'beautiful-mermaid'

export const MERMAID_CARD_CLASS =
  'my-4 w-full max-w-full overflow-hidden rounded-xl border border-border bg-card text-card-foreground'
export const MERMAID_DIAGRAM_SURFACE_CLASS =
  'overflow-auto p-3 [&_svg]:h-auto [&_svg]:max-w-full [&_svg]:mx-auto'
export const QUICK_BUTTON_CLASS =
  'inline-flex h-7 w-7 items-center justify-center rounded-md bg-transparent text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground'
export const MERMAID_TAG_CLASS =
  'inline-flex items-center gap-1.5 rounded-full border border-border/80 bg-muted px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground'

export interface MermaidDiagramProps {
  code: string
  className?: string
  /** When true, wait until `ready` before rendering (streaming messages). */
  streamAware?: boolean
  ready?: boolean
}

export type MermaidRenderResult = {
  svg: string | null
  error: Error | null
}

const MERMAID_TEXT_CONTRAST_STYLE = `
<style data-sandwalk-mermaid-text-contrast="true">
  svg {
    color: hsl(var(--foreground));
  }
  text,
  tspan,
  .nodeLabel,
  .label text,
  .cluster-label text,
  .edgeLabel text,
  .flowchart-label text,
  .messageText,
  .loopText,
  foreignObject div,
  foreignObject span {
    fill: hsl(var(--foreground)) !important;
    color: hsl(var(--foreground)) !important;
    font-weight: 500;
  }
  text,
  tspan,
  .nodeLabel,
  .label text,
  .cluster-label text,
  .edgeLabel text,
  .flowchart-label text {
    paint-order: stroke;
    stroke: hsl(var(--background));
    stroke-width: 2.75px;
    stroke-linejoin: round;
  }
  foreignObject div,
  foreignObject span {
    text-shadow:
      0 0 1px hsl(var(--background)),
      0 0 2px hsl(var(--background)),
      0 0 3px hsl(var(--background));
  }
  .edgeLabel rect,
  .labelBkg {
    fill: hsl(var(--background)) !important;
    fill-opacity: 0.9 !important;
  }
</style>
`

const MERMAID_START =
  /^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram|journey|gantt|pie|mindmap|timeline|gitGraph)\b/i

export function looksLikeMermaid(code: string): boolean {
  return MERMAID_START.test(code.trim())
}

function injectMermaidTextContrastStyle(svg: string): string {
  if (svg.includes('data-sandwalk-mermaid-text-contrast="true"')) {
    return svg
  }
  const svgOpenTag = new RegExp('(' + '<' + 'svg[^>]*>' + ')', 'i')
  return svg.replace(svgOpenTag, `$1${MERMAID_TEXT_CONTRAST_STYLE}`)
}

export function renderMermaid(code: string): MermaidRenderResult {
  try {
    const svg = renderMermaidSVG(code, {
      bg: 'hsl(var(--background))',
      fg: 'hsl(var(--foreground))',
      muted: 'hsl(var(--muted-foreground))',
      border: 'hsl(var(--border))',
      accent: 'hsl(var(--foreground))',
      transparent: true
    })
    return {
      svg: injectMermaidTextContrastStyle(svg),
      error: null
    }
  } catch (error) {
    return {
      svg: null,
      error: error instanceof Error ? error : new Error(String(error))
    }
  }
}
