import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFileContent } from '@sandwalk/agent-ui-core'
import type { ReactNode } from 'react'

import { Skeleton } from '@/components/ui/skeleton'

import { FileActionsHeader } from './FileActionsHeader'
import { FilePreview } from './FilePreview'
import { isStructure } from './workspace-utils'

export function WorkspaceFileContentArea({
  filesTabActive,
  activePath,
  active,
  openingPath,
  draft,
  editorDark,
  isDirty,
  saving,
  status,
  browser,
  client,
  sessionId,
  onSelectFilesTab,
  onCloseTab,
  onOpenModal,
  onDraftChange,
  onSave,
  onAddToChat
}: {
  filesTabActive: boolean
  activePath: string | null
  active: WorkspaceFileContent | null
  openingPath: string | null
  draft: string
  editorDark: boolean
  isDirty: boolean
  saving: boolean
  status: string | null
  browser: ReactNode
  client: LocalAgentClient
  sessionId: string
  onSelectFilesTab: () => void
  onCloseTab: (path: string) => void
  onOpenModal: () => void
  onDraftChange: (value: string) => void
  onSave: () => void
  onAddToChat: (path: string) => void
}) {
  if (filesTabActive) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1">{browser}</div>
        {status ? (
          <div className="text-muted-foreground border-t px-2 py-1 text-[10px]">
            {status}
          </div>
        ) : null}
      </div>
    )
  }

  if (active) {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FileActionsHeader
          path={active.path}
          canSave={active.encoding === 'text' && !isStructure(active.path)}
          dirty={isDirty}
          saving={saving}
          downloadUrl={client.downloadUrl(sessionId, active.path)}
          onAddToChat={() => onAddToChat(active.path)}
          onSave={onSave}
          onExpand={onOpenModal}
          onClose={() => onCloseTab(active.path)}
        />
        <div className="min-h-0 flex-1">
          <FilePreview
            active={active}
            draft={draft}
            editorDark={editorDark}
            onDraftChange={onDraftChange}
            onSave={onSave}
          />
        </div>
        {status ? (
          <div className="text-muted-foreground border-t px-2 py-1 text-[10px]">
            {status}
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <FileActionsHeader
        path={openingPath || activePath || 'file'}
        canSave={false}
        dirty={false}
        saving={false}
        downloadUrl={
          openingPath || activePath
            ? client.downloadUrl(sessionId, openingPath || activePath!)
            : '#'
        }
        onAddToChat={() => {
          if (activePath) onAddToChat(activePath)
        }}
        onSave={() => undefined}
        onExpand={onOpenModal}
        onClose={() => {
          if (activePath) onCloseTab(activePath)
          else onSelectFilesTab()
        }}
      />
      <div
        className="grid min-h-0 flex-1 place-items-center px-6"
        aria-busy="true"
      >
        <div className="w-full max-w-md space-y-3">
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
          <Skeleton className="h-3 w-2/3" />
        </div>
      </div>
    </div>
  )
}
