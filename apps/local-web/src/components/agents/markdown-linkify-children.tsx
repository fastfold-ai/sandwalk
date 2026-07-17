import { Children, Fragment, type ReactNode } from 'react'

import { WorkspaceFileChip } from '@/components/agents/WorkspaceFileChip'
import { splitTextWithWorkspacePaths } from '@/lib/workspace-file-paths'

/** Replace absolute workspace paths in markdown text children with file chips. */
export function linkifyWorkspacePathChildren(
  children: ReactNode,
  onOpenFile?: (path: string) => void,
  workspacePath?: string | null
): ReactNode {
  if (!onOpenFile) return children

  return Children.map(children, (child, index) => {
    if (typeof child !== 'string') return child
    const parts = splitTextWithWorkspacePaths(child, workspacePath)
    if (parts.length === 1 && parts[0]?.type === 'text') return child
    return (
      <Fragment key={`ws-${index}`}>
        {parts.map((part, partIndex) => {
          if (part.type === 'text') {
            return <Fragment key={`t-${partIndex}`}>{part.text}</Fragment>
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
  })
}
