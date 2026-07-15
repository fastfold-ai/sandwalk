import { memo, useMemo } from 'react'

import { MermaidCard } from './mermaid-diagram-card'
import { renderMermaid, type MermaidDiagramProps } from './mermaid-diagram-utils'

export { looksLikeMermaid } from './mermaid-diagram-utils'
export type { MermaidDiagramProps } from './mermaid-diagram-utils'

export const MermaidDiagram = memo(function MermaidDiagram({
  code,
  className,
  streamAware = false,
  ready = true
}: MermaidDiagramProps) {
  const shouldRender = !streamAware || ready
  const renderResult = useMemo(() => {
    if (!shouldRender) return null
    return renderMermaid(code)
  }, [code, shouldRender])

  return (
    <MermaidCard
      code={code}
      className={className}
      renderResult={renderResult}
      isLoading={!shouldRender}
    />
  )
})
