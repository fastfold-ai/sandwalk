import type { LocalAgentClient } from '@sandwalk/agent-local-client'

import { useWorkspaceFileActions } from './use-workspace-file-actions'
import { useWorkspacePanelState } from './use-workspace-panel-state'

export function useWorkspacePanel({
  client,
  sessionId,
  workspaceVersion = 0,
  runActive = false,
  openPathRequest = null,
  onOpenPathRequestHandled,
  onFilesChange,
  onNewFiles
}: {
  client: LocalAgentClient
  sessionId: string
  workspaceVersion?: number
  runActive?: boolean
  openPathRequest?: string | null
  onOpenPathRequestHandled?: () => void
  onFilesChange?: (count: number) => void
  onNewFiles?: (files: import('@sandwalk/agent-ui-core').WorkspaceFile[]) => void
}) {
  const state = useWorkspacePanelState({
    client,
    sessionId,
    workspaceVersion,
    runActive,
    onFilesChange,
    onNewFiles
  })
  const actions = useWorkspaceFileActions(state, {
    openPathRequest,
    onOpenPathRequestHandled
  })

  return {
    tabs: state.tabs,
    activePath: state.activePath,
    activeTab: state.activeTab,
    active: state.active,
    openingPath: state.openingPath,
    draft: state.draft,
    status: state.status,
    saving: state.saving,
    refreshing: state.refreshing,
    reloading: state.reloading,
    isDirty: state.isDirty,
    pathDialog: state.pathDialog,
    pathValue: state.pathValue,
    pathBusy: state.pathBusy,
    fileTabMenu: state.fileTabMenu,
    fileBrowserMenu: state.fileBrowserMenu,
    renameFilePath: state.renameFilePath,
    renameFileValue: state.renameFileValue,
    deleteFilePath: state.deleteFilePath,
    deleteFileBusy: state.deleteFileBusy,
    moveSourcePath: state.moveSourcePath,
    moveBusy: state.moveBusy,
    renameDialogPath: state.renameDialogPath,
    renameDialogValue: state.renameDialogValue,
    renameDialogBusy: state.renameDialogBusy,
    query: state.query,
    viewMode: state.viewMode,
    expandedGroups: state.expandedGroups,
    expandedDirs: state.expandedDirs,
    modalOpen: state.modalOpen,
    filesTabActive: state.filesTabActive,
    editorDark: state.editorDark,
    uploadRef: state.uploadRef,
    renameFileInputRef: state.renameFileInputRef,
    renameFileIgnoreBlurRef: state.renameFileIgnoreBlurRef,
    groups: state.groups,
    filteredFiles: state.filteredFiles,
    artifactFiles: state.artifactFiles,
    files: state.files,
    setQuery: state.setQuery,
    setViewMode: state.setViewMode,
    setExpandedGroups: state.setExpandedGroups,
    setExpandedDirs: state.setExpandedDirs,
    setModalOpen: state.setModalOpen,
    setFileTabMenu: state.setFileTabMenu,
    setFileBrowserMenu: state.setFileBrowserMenu,
    setPathValue: state.setPathValue,
    setRenameFileValue: state.setRenameFileValue,
    setRenameDialogValue: state.setRenameDialogValue,
    setDeleteFilePath: state.setDeleteFilePath,
    setDraft: state.setDraft,
    refresh: state.refresh,
    save: state.save,
    ...actions
  }
}
