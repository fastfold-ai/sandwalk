import type { LocalAgentClient } from '@sandwalk/agent-local-client'

import { useWorkspaceFileActions } from './use-workspace-file-actions'
import { useWorkspacePanelState } from './use-workspace-panel-state'

export function useWorkspacePanel({
  client,
  sessionId,
  workspaceVersion = 0,
  openPathRequest = null,
  onOpenPathRequestHandled,
  onFilesChange
}: {
  client: LocalAgentClient
  sessionId: string
  workspaceVersion?: number
  openPathRequest?: string | null
  onOpenPathRequestHandled?: () => void
  onFilesChange?: (count: number) => void
}) {
  const state = useWorkspacePanelState({
    client,
    sessionId,
    workspaceVersion,
    onFilesChange
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
    isDirty: state.isDirty,
    pathDialog: state.pathDialog,
    pathValue: state.pathValue,
    pathBusy: state.pathBusy,
    fileTabMenu: state.fileTabMenu,
    renameFilePath: state.renameFilePath,
    renameFileValue: state.renameFileValue,
    deleteFilePath: state.deleteFilePath,
    deleteFileBusy: state.deleteFileBusy,
    query: state.query,
    viewMode: state.viewMode,
    expandedGroups: state.expandedGroups,
    modalOpen: state.modalOpen,
    filesTabActive: state.filesTabActive,
    editorDark: state.editorDark,
    uploadRef: state.uploadRef,
    renameFileInputRef: state.renameFileInputRef,
    renameFileIgnoreBlurRef: state.renameFileIgnoreBlurRef,
    groups: state.groups,
    filteredFiles: state.filteredFiles,
    artifactFiles: state.artifactFiles,
    setQuery: state.setQuery,
    setViewMode: state.setViewMode,
    setExpandedGroups: state.setExpandedGroups,
    setModalOpen: state.setModalOpen,
    setFileTabMenu: state.setFileTabMenu,
    setPathValue: state.setPathValue,
    setRenameFileValue: state.setRenameFileValue,
    setDeleteFilePath: state.setDeleteFilePath,
    setDraft: state.setDraft,
    refresh: state.refresh,
    save: state.save,
    ...actions
  }
}
