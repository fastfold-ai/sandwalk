import type { WorkspaceFileContent } from '@sandwalk/agent-ui-core'
import { Folder, Maximize2, X } from 'lucide-react'
import type { MutableRefObject, RefObject } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function WorkspaceFileTabsBar({
  tabs,
  filesTabActive,
  activePath,
  openingPath,
  renameFilePath,
  renameFileValue,
  uploadRef,
  renameFileInputRef,
  renameFileIgnoreBlurRef,
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
  onUploadChange
}: {
  tabs: WorkspaceFileContent[]
  filesTabActive: boolean
  activePath: string | null
  openingPath: string | null
  renameFilePath: string | null
  renameFileValue: string
  uploadRef: RefObject<HTMLInputElement | null>
  renameFileInputRef: RefObject<HTMLInputElement | null>
  renameFileIgnoreBlurRef: MutableRefObject<boolean>
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
  onUploadChange: (files: FileList | null) => void
}) {
  return (
    // Match session header (h-11) and stay above the shell drag overlay (z-10)
    // so the Files tab isn't clipped / unclickable on first paint.
    <div className="relative z-20 flex h-11 shrink-0 items-center gap-1 px-1.5">
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
  )
}
