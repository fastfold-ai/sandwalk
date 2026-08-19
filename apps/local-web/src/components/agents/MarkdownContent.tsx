import { memo, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import { useNavigate } from 'react-router-dom'
import remarkGfm from 'remark-gfm'

import type { SkillIconSkill } from '@/components/agents/SkillMentionChip'
import type { AgentSession } from '@sandwalk/agent-ui-core'
import { cn } from '@/lib/utils'

import { buildMarkdownComponents } from './markdown-components'
import { ensureMermaidFences } from './markdown-mermaid-fences'

export { ensureMermaidFences } from './markdown-mermaid-fences'

/** While streaming, long single-paragraph dumps read as a wall of text. */
function loosenStreamingParagraphs(content: string): string {
  if (!content.trim() || content.includes('\n\n')) return content
  return content.replace(/([.!?])\s+(?=[A-Z“"([])/g, '$1\n\n')
}

export const MarkdownContent = memo(function MarkdownContent({
  content,
  className,
  streaming = false,
  onOpenFile,
  workspacePath,
  skills,
  mentionChats
}: {
  content: string
  className?: string
  /** When true, Mermaid waits until the message finishes streaming. */
  streaming?: boolean
  /** Open a workspace-relative path in the Files panel. */
  onOpenFile?: (path: string) => void
  /** Absolute session workspace root, used to recognize in-workspace paths. */
  workspacePath?: string | null
  /** Installed skills for custom / featured chip icons in chat. */
  skills?: SkillIconSkill[]
  mentionChats?: AgentSession[]
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
        workspacePath,
        skills,
        mentionChats
      }),
    [mentionChats, navigate, streaming, onOpenFile, workspacePath, skills]
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
