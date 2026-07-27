import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useEffect, useRef, useState } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'

import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup
} from '@/components/ui/resizable'
import { cn } from '@/lib/utils'

import { ArtifactsBrowser } from './ArtifactsBrowser'
import { TerminalPanel } from './TerminalPanel'
import { useWorkspacePanel } from './workspace/use-workspace-panel'
import { WorkspaceFileBrowserContextMenu } from './workspace/workspace-file-browser-context-menu'
import { WorkspaceFileTabContextMenu } from './workspace/workspace-file-tab-context-menu'
import {
  WorkspaceDeleteFileDialog,
  WorkspaceMoveFileDialog,
  WorkspacePathDialog,
  WorkspaceRenameDialog
} from './workspace/workspace-panel-dialogs'
import { WorkspaceArtifactsModal } from './WorkspaceArtifactsModal'
import { WorkspaceFileTabsColumn } from './WorkspaceFileTabsColumn'

export function WorkspacePanel({
  client,
  sessionId,
  workspacePath = null,
  workspaceVersion = 0,
  runActive = false,
  openPathRequest = null,
  onOpenPathRequestHandled,
  onAddToChat,
  onBuildPlan,
  onFilesChange,
  onNewFiles,
  onTogglePanel,
  terminalOpen = false,
  onCloseTerminal,
  onOpenTerminal
}: {
  client: LocalAgentClient
  sessionId: string
  workspacePath?: string | null
  workspaceVersion?: number
  runActive?: boolean
  /** When set, open this workspace path in a preview tab. */
  openPathRequest?: string | null
  onOpenPathRequestHandled?: () => void
  onAddToChat: (path: string) => void
  onBuildPlan?: (path: string) => void
  onFilesChange?: (count: number) => void
  onNewFiles?: (
    files: import('@sandwalk/agent-ui-core').WorkspaceFile[]
  ) => void
  onTogglePanel?: () => void
  terminalOpen?: boolean
  onCloseTerminal?: () => void
  onOpenTerminal?: () => void
}) {
  const workspace = useWorkspacePanel({
    client,
    sessionId,
    workspaceVersion,
    runActive,
    openPathRequest,
    onOpenPathRequestHandled,
    onFilesChange,
    onNewFiles
  })

  /** Keep terminal mounted after first open so toggle doesn't drop the PTY socket. */
  const [terminalMounted, setTerminalMounted] = useState(terminalOpen)
  const terminalPanelRef = useRef<ImperativePanelHandle>(null)

  useEffect(() => {
    if (terminalOpen) setTerminalMounted(true)
  }, [terminalOpen])

  useEffect(() => {
    const panel = terminalPanelRef.current
    if (!panel || !terminalMounted) return
    if (terminalOpen) {
      if (panel.isCollapsed()) panel.expand(50)
    } else if (!panel.isCollapsed()) {
      panel.collapse()
    }
  }, [terminalOpen, terminalMounted])

  const browser = (
    <ArtifactsBrowser
      client={client}
      sessionId={sessionId}
      groups={workspace.groups}
      totalCount={workspace.filteredFiles.length}
      query={workspace.query}
      viewMode={workspace.viewMode}
      flatMode={workspace.flatMode}
      expandedGroups={workspace.expandedGroups}
      activePath={workspace.activePath}
      workspacePath={workspacePath}
      empty={
        workspace.artifactFiles.length === 0 && workspace.groups.length === 0
      }
      onQueryChange={workspace.setQuery}
      onViewModeChange={workspace.setViewMode}
      onFlatModeChange={workspace.setFlatMode}
      onToggleGroup={id =>
        workspace.setExpandedGroups(current => ({
          ...current,
          [id]: !(current[id] ?? true)
        }))
      }
      onOpenFile={file => void workspace.openFile(file)}
      onDownloadFile={workspace.downloadFile}
      onDownloadAll={workspace.downloadAll}
      onUpload={() => workspace.uploadRef.current?.click()}
      onNewFile={() => workspace.openPathDialog('file')}
      onNewFolder={() => workspace.openPathDialog('folder')}
      onRefresh={() => void workspace.refresh()}
      refreshing={workspace.refreshing}
      onFileContextMenu={(file, x, y) =>
        workspace.setFileBrowserMenu({
          path: file.path,
          x,
          y,
          type: file.type === 'directory' ? 'directory' : 'file'
        })
      }
    />
  )

  const filesColumn = (
    <WorkspaceFileTabsColumn
      tabs={workspace.tabs}
      filesTabActive={workspace.filesTabActive}
      activePath={workspace.activePath}
      active={workspace.active}
      openingPath={workspace.openingPath}
      renameFilePath={workspace.renameFilePath}
      renameFileValue={workspace.renameFileValue}
      draft={workspace.draft}
      editorDark={workspace.editorDark}
      isDirty={workspace.isDirty}
      saving={workspace.saving}
      reloading={workspace.reloading}
      status={workspace.status}
      uploadRef={workspace.uploadRef}
      renameFileInputRef={workspace.renameFileInputRef}
      renameFileIgnoreBlurRef={workspace.renameFileIgnoreBlurRef}
      browser={browser}
      client={client}
      sessionId={sessionId}
      onTogglePanel={onTogglePanel}
      onSelectFilesTab={workspace.selectFilesTab}
      onSelectFileTab={workspace.selectFileTab}
      onCloseTab={workspace.closeTab}
      onOpenModal={() => workspace.setModalOpen(true)}
      onFileTabContextMenu={(path, x, y) =>
        workspace.setFileTabMenu({ path, x, y })
      }
      onRenameFileValueChange={workspace.setRenameFileValue}
      onSubmitRenameFile={() => void workspace.submitRenameFile()}
      onCancelRenameFile={workspace.cancelRenameFile}
      onCommitRenameFileFromBlur={workspace.commitRenameFileFromBlur}
      onBeginRenameFile={workspace.beginRenameFile}
      onDraftChange={workspace.setDraft}
      onSave={() => void workspace.save()}
      onReload={workspace.reloadActiveFile}
      onDownload={() => {
        if (workspace.activePath) workspace.downloadFileTab(workspace.activePath)
      }}
      onAddToChat={onAddToChat}
      onBuildPlan={onBuildPlan}
      onUploadChange={workspace.handleUploadChange}
    />
  )

  return (
    <>
      <aside className="bg-card relative z-20 flex h-full w-full min-w-0 flex-col">
        {terminalMounted ? (
          <ResizablePanelGroup
            direction="vertical"
            autoSaveId="fastfold.files-terminal-panels"
            className="h-full"
          >
            <ResizablePanel
              id="files"
              order={1}
              defaultSize={50}
              minSize={20}
              className="min-h-0"
            >
              <div className="flex h-full min-h-0 flex-col overflow-hidden">
                {filesColumn}
              </div>
            </ResizablePanel>
            <ResizableHandle
              className={cn(
                'bg-transparent after:bg-transparent',
                !terminalOpen && 'pointer-events-none opacity-0'
              )}
            />
            <ResizablePanel
              id="terminal"
              order={2}
              ref={terminalPanelRef}
              collapsible
              collapsedSize={0}
              defaultSize={terminalOpen ? 50 : 0}
              minSize={15}
              className="min-h-0"
              onCollapse={() => onCloseTerminal?.()}
              onExpand={() => onOpenTerminal?.()}
            >
              <TerminalPanel
                client={client}
                sessionId={sessionId}
                visible={terminalOpen}
                onClose={onCloseTerminal}
              />
            </ResizablePanel>
          </ResizablePanelGroup>
        ) : (
          filesColumn
        )}
      </aside>

      <WorkspaceArtifactsModal
        open={workspace.modalOpen}
        onOpenChange={workspace.setModalOpen}
        browser={browser}
        activeTab={workspace.activeTab}
        openingPath={workspace.openingPath}
        activePath={workspace.activePath}
        draft={workspace.draft}
        editorDark={workspace.editorDark}
        client={client}
        sessionId={sessionId}
        onUpload={() => workspace.uploadRef.current?.click()}
        onRefresh={() => void workspace.refresh()}
        onReload={workspace.reloadActiveFile}
        reloading={workspace.reloading}
        onAddToChat={onAddToChat}
        onBuildPlan={onBuildPlan}
        onDraftChange={workspace.setDraft}
        onSave={() => void workspace.save()}
        onDownload={workspace.downloadFile}
      />

      <WorkspacePathDialog
        kind={workspace.pathDialog}
        value={workspace.pathValue}
        busy={workspace.pathBusy}
        onValueChange={workspace.setPathValue}
        onClose={workspace.closePathDialog}
        onSubmit={() => void workspace.submitPathDialog()}
      />

      <WorkspaceDeleteFileDialog
        path={workspace.deleteFilePath}
        busy={workspace.deleteFileBusy}
        isDirectory={
          workspace.files.find(
            item => item.path === workspace.deleteFilePath
          )?.type === 'directory'
        }
        onClose={() => workspace.setDeleteFilePath(null)}
        onConfirm={() => void workspace.submitDeleteFile()}
      />

      <WorkspaceMoveFileDialog
        sourcePath={workspace.moveSourcePath}
        folders={workspace.files
          .filter(item => item.type === 'directory')
          .map(item => item.path)
          .sort((a, b) => a.localeCompare(b))}
        busy={workspace.moveBusy}
        onClose={workspace.closeMoveDialog}
        onSubmit={folder => void workspace.submitMoveToFolder(folder)}
      />

      <WorkspaceRenameDialog
        path={workspace.renameDialogPath}
        value={workspace.renameDialogValue}
        busy={workspace.renameDialogBusy}
        onValueChange={workspace.setRenameDialogValue}
        onClose={workspace.closeRenameDialog}
        onSubmit={() => void workspace.submitRenameDialog()}
      />

      {workspace.fileTabMenu &&
      workspace.tabs.some(tab => tab.path === workspace.fileTabMenu?.path) ? (
        <WorkspaceFileTabContextMenu
          menu={workspace.fileTabMenu}
          tabCount={workspace.tabs.length}
          onClose={() => workspace.setFileTabMenu(null)}
          onCloseTab={workspace.closeTab}
          onCloseOtherTabs={workspace.closeOtherTabs}
          onRename={workspace.beginRenameFile}
          onMove={workspace.openMoveDialog}
          onDownload={workspace.downloadFileTab}
          onDelete={workspace.setDeleteFilePath}
        />
      ) : null}

      <WorkspaceFileBrowserContextMenu
        menu={workspace.fileBrowserMenu}
        onClose={() => workspace.setFileBrowserMenu(null)}
        onAddToChat={onAddToChat}
        onRename={workspace.openRenameDialog}
        onMove={workspace.openMoveDialog}
        onDownload={workspace.downloadFile}
        onDelete={workspace.setDeleteFilePath}
      />
    </>
  )
}
