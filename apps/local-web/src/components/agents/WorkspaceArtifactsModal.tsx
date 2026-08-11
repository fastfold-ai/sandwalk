import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFileContent } from '@sandwalk/agent-ui-core'
import { Download, Folder, RefreshCw, Upload, X } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTitle
} from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'

import { FilePreview } from './FilePreview'
import { isStructure } from './workspace-utils'

export function WorkspaceArtifactsModal({
  open,
  onOpenChange,
  browser,
  activeTab,
  openingPath,
  activePath,
  draft,
  editorDark,
  client: _client,
  sessionId: _sessionId,
  onUpload,
  onRefresh,
  onReload,
  reloading = false,
  onAddToChat,
  onBuildPlan,
  onDraftChange,
  onSave,
  onDownload
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  browser: ReactNode
  activeTab: WorkspaceFileContent | null
  openingPath: string | null
  activePath: string | null
  draft: string
  editorDark: boolean
  client: LocalAgentClient
  sessionId: string
  onUpload: () => void
  onRefresh: () => void
  onReload?: () => void
  reloading?: boolean
  onAddToChat: (path: string) => void
  onBuildPlan?: (path: string) => void
  onDraftChange: (value: string) => void
  onSave: () => void
  onDownload?: (path: string) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        hideCloseButton
        className="flex h-[min(90vh,52rem)] w-[min(96vw,72rem)] max-w-none flex-col gap-0 overflow-hidden p-0"
      >
        <div className="flex h-12 shrink-0 items-center justify-between border-b px-4">
          <div className="flex items-center gap-2">
            <Folder className="text-muted-foreground size-4" />
            <DialogTitle className="text-sm font-medium">Artifacts</DialogTitle>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              title="Upload"
              onClick={onUpload}
            >
              <Upload className="size-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-8"
              title="Refresh"
              onClick={onRefresh}
            >
              <RefreshCw className="size-4" />
            </Button>
            <DialogClose asChild>
              <Button
                variant="ghost"
                size="icon"
                className="size-8"
                title="Close"
                aria-label="Close"
              >
                <X className="size-4" />
              </Button>
            </DialogClose>
          </div>
        </div>
        <div className="flex min-h-0 flex-1">
          <div className="flex w-[22rem] shrink-0 flex-col border-r">
            {browser}
          </div>
          <div className="flex min-w-0 flex-1 flex-col">
            {activeTab ? (
              <>
                <div className="flex h-10 shrink-0 items-center justify-between border-b px-3">
                  <span className="text-muted-foreground truncate text-xs">
                    {activeTab.path}
                  </span>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 text-[11px]"
                      onClick={() => onAddToChat(activeTab.path)}
                    >
                      Add to chat
                    </Button>
                    {onReload ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7"
                        title="Reload file"
                        aria-label="Reload file"
                        disabled={reloading}
                        onClick={onReload}
                      >
                        <RefreshCw
                          className={`size-3.5 ${reloading ? 'animate-spin' : ''}`}
                        />
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-7"
                      title="Download"
                      aria-label="Download"
                      onClick={() => onDownload?.(activeTab.path)}
                    >
                      <Download className="size-3.5" />
                    </Button>
                  </div>
                </div>
                <div className="min-h-0 flex-1">
                  <FilePreview
                    active={activeTab}
                    draft={draft}
                    editorDark={editorDark}
                    onDraftChange={onDraftChange}
                    onSave={
                      activeTab.encoding === 'text' &&
                      !isStructure(activeTab.path)
                        ? onSave
                        : undefined
                    }
                    onBuildPlan={onBuildPlan}
                  />
                </div>
              </>
            ) : openingPath || activePath ? (
              <div
                className="grid flex-1 place-items-center px-6"
                aria-busy="true"
              >
                <div className="w-full max-w-md space-y-3">
                  <Skeleton className="h-4 w-1/3" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-5/6" />
                  <Skeleton className="h-3 w-2/3" />
                </div>
              </div>
            ) : (
              <div className="text-muted-foreground/70 grid flex-1 place-items-center text-xs">
                Select a file to preview
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
