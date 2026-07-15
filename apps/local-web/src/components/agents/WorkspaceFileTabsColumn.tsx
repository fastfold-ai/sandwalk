import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { WorkspaceFileContent } from '@sandwalk/agent-ui-core'
import type { MutableRefObject, ReactNode, RefObject } from 'react'

import { WorkspaceFileContentArea } from './workspace-file-content-area'
import { WorkspaceFileTabsBar } from './workspace-file-tabs-bar'

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
      <WorkspaceFileTabsBar
        tabs={tabs}
        filesTabActive={filesTabActive}
        activePath={activePath}
        openingPath={openingPath}
        renameFilePath={renameFilePath}
        renameFileValue={renameFileValue}
        uploadRef={uploadRef}
        renameFileInputRef={renameFileInputRef}
        renameFileIgnoreBlurRef={renameFileIgnoreBlurRef}
        onTogglePanel={onTogglePanel}
        onSelectFilesTab={onSelectFilesTab}
        onSelectFileTab={onSelectFileTab}
        onCloseTab={onCloseTab}
        onOpenModal={onOpenModal}
        onFileTabContextMenu={onFileTabContextMenu}
        onRenameFileValueChange={onRenameFileValueChange}
        onSubmitRenameFile={onSubmitRenameFile}
        onCancelRenameFile={onCancelRenameFile}
        onCommitRenameFileFromBlur={onCommitRenameFileFromBlur}
        onBeginRenameFile={onBeginRenameFile}
        onUploadChange={onUploadChange}
      />
      <WorkspaceFileContentArea
        filesTabActive={filesTabActive}
        activePath={activePath}
        active={active}
        openingPath={openingPath}
        draft={draft}
        editorDark={editorDark}
        isDirty={isDirty}
        saving={saving}
        status={status}
        browser={browser}
        client={client}
        sessionId={sessionId}
        onSelectFilesTab={onSelectFilesTab}
        onCloseTab={onCloseTab}
        onOpenModal={onOpenModal}
        onDraftChange={onDraftChange}
        onSave={onSave}
        onAddToChat={onAddToChat}
      />
    </>
  )
}
