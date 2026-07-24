import { Children, Fragment, type ReactNode } from 'react'

import { SkillMentionChip } from '@/components/agents/SkillMentionChip'
import { WorkspaceFileChip } from '@/components/agents/WorkspaceFileChip'
import { splitTextWithSkillMentions } from '@/lib/skill-mentions'
import { splitTextWithWorkspacePaths } from '@/lib/workspace-file-paths'

function linkifySkillSegments(text: string): ReactNode[] {
  const skillParts = splitTextWithSkillMentions(text)
  return skillParts.map((part, partIndex) => {
    if (part.type === 'text') {
      return <Fragment key={`st-${partIndex}`}>{part.text}</Fragment>
    }
    return (
      <SkillMentionChip
        key={`sk-${partIndex}-${part.name}`}
        name={part.name}
      />
    )
  })
}

/** Replace workspace paths and skill mentions in markdown text children. */
export function linkifyWorkspacePathChildren(
  children: ReactNode,
  onOpenFile?: (path: string) => void,
  workspacePath?: string | null
): ReactNode {
  return Children.map(children, (child, index) => {
    if (typeof child !== 'string') return child

    if (onOpenFile) {
      const parts = splitTextWithWorkspacePaths(child, workspacePath)
      const hasFile = parts.some(part => part.type === 'file')
      if (hasFile) {
        return (
          <Fragment key={`ws-${index}`}>
            {parts.map((part, partIndex) => {
              if (part.type === 'text') {
                return (
                  <Fragment key={`t-${partIndex}`}>
                    {linkifySkillSegments(part.text)}
                  </Fragment>
                )
              }
              return (
                <WorkspaceFileChip
                  key={`f-${partIndex}-${part.relative}`}
                  path={part.relative}
                  onOpenFile={onOpenFile}
                />
              )
            })}
          </Fragment>
        )
      }
    }

    const skillParts = splitTextWithSkillMentions(child)
    if (skillParts.length === 1 && skillParts[0]?.type === 'text') {
      return child
    }
    return (
      <Fragment key={`sk-wrap-${index}`}>
        {linkifySkillSegments(child)}
      </Fragment>
    )
  })
}
