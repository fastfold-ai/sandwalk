import { memo, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { useNavigate } from 'react-router-dom'
import remarkGfm from 'remark-gfm'

import { cn } from '@/lib/utils'

import { ensureMermaidFences } from './markdown-mermaid-fences'
import { buildMarkdownComponents } from './markdown-components'

export { ensureMermaidFences } from './markdown-mermaid-fences'

/** While streaming, long single-paragraph dumps read as a wall of text. */
function loosenStreamingParagraphs(content: string): string {
  if (!content.trim() || content.includes('\n\n')) return content
  return content.replace(/([.!?])\s+(?=[A-Z“"(\[])/g, '$1\n\n')
}

export const MarkdownContent = memo(function MarkdownContent({
  content,
  className,
  streaming = false,
  onOpenFile,
  workspacePath
}: {
  content: string
  className?: string
  /** When true, Mermaid waits until the message finishes streaming. */
  streaming?: boolean
  /** Open a workspace-relative path in the Files panel. */
  onOpenFile?: (path: string) => void
  /** Absolute session workspace root, used to recognize in-workspace paths. */
  workspacePath?: string | null
}) {
  const navigate = useNavigate()
  const prepared = useMemo(() => {
    const fenced = ensureMermaidFences(content)
    return streaming ? loosenStreamingParagraphs(fenced) : fenced
  }, [content, streaming])
  const components = useMemo(
    () =>
      buildMarkdownComponents({
        navigate,
        streaming,
        onOpenFile,
        workspacePath
      }),
    [navigate, streaming, onOpenFile, workspacePath]
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
