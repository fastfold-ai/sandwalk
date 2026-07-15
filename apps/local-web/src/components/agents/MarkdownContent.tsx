import { memo, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { useNavigate } from 'react-router-dom'
import remarkGfm from 'remark-gfm'

import { cn } from '@/lib/utils'

import { ensureMermaidFences } from './markdown-mermaid-fences'
import { buildMarkdownComponents } from './markdown-components'

export { ensureMermaidFences } from './markdown-mermaid-fences'

export const MarkdownContent = memo(function MarkdownContent({
  content,
  className,
  streaming = false
}: {
  content: string
  className?: string
  /** When true, Mermaid waits until the message finishes streaming. */
  streaming?: boolean
}) {
  const navigate = useNavigate()
  const prepared = useMemo(() => ensureMermaidFences(content), [content])
  const components = useMemo(
    () => buildMarkdownComponents(navigate, streaming),
    [navigate, streaming]
  )

  return (
    <div
      className={cn(
        'text-foreground max-w-none break-words [&_a]:underline [&_a]:underline-offset-2',
        className
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {prepared}
      </ReactMarkdown>
    </div>
  )
})
