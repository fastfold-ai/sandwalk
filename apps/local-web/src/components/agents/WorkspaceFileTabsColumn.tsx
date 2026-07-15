import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFileContent } from '@sandwalk/agent-ui-core'
import { Folder, Maximize2, X } from 'lucide-react'
import type { MutableRefObject, ReactNode, RefObject } from 'react'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

import { FileActionsHeader } from './FileActionsHeader'
import { FilePreview } from './FilePreview'
import { isStructure } from './workspace-utils'

export function WorkspaceFileTabsColumn({
  tabs,
  filesTabActive,
  activePath,
  active,
  openingPath,
  renameFilePath,
  renameFileValue,
  draft,
  editorDark,
  isDirty,
  saving,
  status,
  uploadRef,
  renameFileInputRef,
  renameFileIgnoreBlurRef,
  browser,
  client,
  sessionId,
  onTogglePanel,
  onSelectFilesTab,
  onSelectFileTab,
  onCloseTab,
  onOpenModal,
  onFileTabContextMenu,
  onRenameFileValueChange,
  onSubmitRenameFile,
  onCancelRenameFile,
  onCommitRenameFileFromBlur,
  onBeginRenameFile,
  onDraftChange,
  onSave,
  onAddToChat,
  onUploadChange
}: {
  tabs: WorkspaceFileContent[]
  filesTabActive: boolean
  activePath: string | null
  active: WorkspaceFileContent | null
  openingPath: string | null
  renameFilePath: string | null
  renameFileValue: string
  draft: string
  editorDark: boolean
  isDirty: boolean
  saving: boolean
  status: string | null
  uploadRef: RefObject<HTMLInputElement | null>
  renameFileInputRef: RefObject<HTMLInputElement | null>
  renameFileIgnoreBlurRef: MutableRefObject<boolean>
  browser: ReactNode
  client: LocalAgentClient
  sessionId: string
  onTogglePanel?: () => void
  onSelectFilesTab: () => void
  onSelectFileTab: (path: string) => void
  onCloseTab: (path: string) => void
  onOpenModal: () => void
  onFileTabContextMenu: (path: string, x: number, y: number) => void
  onRenameFileValueChange: (value: string) => void
  onSubmitRenameFile: () => void
  onCancelRenameFile: () => void
  onCommitRenameFileFromBlur: () => void
  onBeginRenameFile: (path: string) => void
  onDraftChange: (value: string) => void
  onSave: () => void
  onAddToChat: (path: string) => void
  onUploadChange: (files: FileList | null) => void
}) {
  return (
    <>
      <div className="flex h-10 shrink-0 items-center gap-1 px-1.5">
        <div className="chat-scrollbar-x flex min-w-0 flex-1 items-stretch gap-0.5 overflow-x-auto">
          <div
            className={cn(
              'group relative my-auto flex h-8 shrink-0 items-center gap-1.5 rounded-md px-2.5',
              filesTabActive
                ? 'bg-muted text-foreground'
                : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground'
            )}
          >
            <button
              type="button"
              className="inline-flex items-center gap-1.5 text-xs font-medium"
              onClick={onSelectFilesTab}
            >
              <Folder className="size-3.5 shrink-0" />
              Files
            </button>
            {onTogglePanel ? (
              <button
                type="button"
                className="bg-muted hover:bg-background/80 absolute right-0.5 top-1/2 inline-flex size-5 -translate-y-1/2 items-center justify-center rounded-sm opacity-0 group-hover:opacity-100"
                aria-label="Close files panel"
                onClick={event => {
                  event.stopPropagation()
                  onTogglePanel()
                }}
              >
                <X className="size-3.5" />
              </button>
            ) : null}
          </div>
          {tabs.map(tab => {
            const name = tab.path.split('/').at(-1) || tab.path
            const selected = !filesTabActive && activePath === tab.path
            const renaming = renameFilePath === tab.path
            return (
              <div
                key={tab.path}
                className={cn(
                  'group relative my-auto flex h-8 max-w-[180px] shrink-0 items-center rounded-md px-2.5',
                  selected || renaming
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                  renaming && 'max-w-[220px] pr-1.5'
                )}
                onContextMenu={event => {
                  if (renaming) return
                  event.preventDefault()
                  onFileTabContextMenu(tab.path, event.clientX, event.clientY)
                }}
              >
                {renaming ? (
                  <input
                    ref={renameFileInputRef}
                    className="bg-background text-foreground h-6 w-full min-w-[6rem] rounded border px-1.5 text-xs font-medium outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    value={renameFileValue}
                    onFocus={event => event.currentTarget.select()}
                    onChange={event => onRenameFileValueChange(event.target.value)}
                    onClick={event => event.stopPropagation()}
                    onKeyDown={event => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        event.stopPropagation()
                        renameFileIgnoreBlurRef.current = true
                        onSubmitRenameFile()
                      } else if (event.key === 'Escape') {
                        event.preventDefault()
                        event.stopPropagation()
                        onCancelRenameFile()
                      }
                    }}
                    onBlur={() => onCommitRenameFileFromBlur()}
                  />
                ) : (
                  <>
                    <button
                      type="button"
                      className="max-w-full truncate pr-0 text-left text-xs font-medium"
                      title={tab.path}
                      onClick={() => onSelectFileTab(tab.path)}
                      onDoubleClick={event => {
                        event.preventDefault()
                        onBeginRenameFile(tab.path)
                      }}
                    >
                      {name}
                    </button>
                    <button
                      type="button"
                      className="bg-muted hover:bg-background/80 absolute right-0.5 top-1/2 inline-flex size-5 -translate-y-1/2 items-center justify-center rounded-sm opacity-0 group-hover:opacity-100"
                      aria-label={`Close ${name}`}
                      onClick={event => {
                        event.stopPropagation()
                        onCloseTab(tab.path)
                      }}
                    >
                      <X className="size-3.5" />
                    </button>
                  </>
                )}
              </div>
            )
          })}
          {openingPath && !tabs.some(tab => tab.path === openingPath) ? (
            <div className="bg-muted text-foreground my-auto flex h-8 max-w-[180px] shrink-0 items-center rounded-md px-2.5">
              <span
                className="max-w-full truncate text-xs font-medium"
                title={openingPath}
              >
                {openingPath.split('/').at(-1) || openingPath}
              </span>
            </div>
          ) : null}
        </div>
        <div className="ml-auto flex shrink-0 items-center">
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            title="Open full screen"
            onClick={onOpenModal}
          >
            <Maximize2 className="size-3.5" />
          </Button>
          {onTogglePanel ? (
            <Button
              variant="ghost"
              size="icon"
              className="size-7"
              title="Hide files panel"
              aria-label="Hide files panel"
              onClick={onTogglePanel}
            >
              <X className="size-3.5" />
            </Button>
          ) : null}
        </div>
        <input
          ref={uploadRef}
          hidden
          type="file"
          multiple
          onChange={event => {
            onUploadChange(event.target.files)
            event.target.value = ''
          }}
        />
      </div>

      {filesTabActive ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">{browser}</div>
          {status ? (
            <div className="text-muted-foreground border-t px-2 py-1 text-[10px]">
              {status}
            </div>
          ) : null}
        </div>
      ) : active ? (
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
      ) : (
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
      )}
    </>
  )
}
