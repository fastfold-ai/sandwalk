import type { AgentSkillDetail, WorkspaceFile } from '@sandwalk/agent-ui-core'
import { useRef, useState } from 'react'
import type { ImperativePanelHandle } from 'react-resizable-panels'

import {
  FILES_PANEL_COLLAPSED_STORAGE_KEY,
  readCollapsedSidebarSections,
  readLastSessionByScope,
  readOpenTabsByProject,
  readProjectScopeId,
  readRecentProjectIds,
  SIDEBAR_COLLAPSED_STORAGE_KEY,
  TERMINAL_OPEN_STORAGE_KEY
} from '@/lib/app-storage'

export function useAppUiState() {
  const [connectionLimitDismissed, setConnectionLimitDismissed] =
    useState(false)
  const [newProjectOpen, setNewProjectOpen] = useState(false)
  const [projectSettingsOpen, setProjectSettingsOpen] = useState(false)
  const [projectScopeId, setProjectScopeId] = useState<string | null>(() =>
    readProjectScopeId()
  )
  const [lastSessionByScope, setLastSessionByScope] = useState<
    Record<string, string>
  >(() => readLastSessionByScope())
  const [recentProjectIds, setRecentProjectIds] = useState<string[]>(() =>
    readRecentProjectIds()
  )
  const [skillDetail, setSkillDetail] = useState<AgentSkillDetail | null>(null)
  const [globalSearchOpen, setGlobalSearchOpen] = useState(false)
  const [pendingOpenPath, setPendingOpenPath] = useState<string | null>(null)
  const pendingMentionRef = useRef<string | string[] | null>(null)
  const pendingAttachmentsRef = useRef<{
    sessionId: string
    paths: string[]
  } | null>(null)
  const sidebarPanelRef = useRef<ImperativePanelHandle>(null)
  const filesPanelRef = useRef<ImperativePanelHandle>(null)
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)
  const [copiedResumeCommand, setCopiedResumeCommand] = useState(false)
  const [cliMenuOpen, setCliMenuOpen] = useState(false)
  const [terminalOpen, setTerminalOpen] = useState(() => {
    try {
      return localStorage.getItem(TERMINAL_OPEN_STORAGE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [filesPanelCollapsed, setFilesPanelCollapsed] = useState(() => {
    try {
      // Default closed; only reopen when the user explicitly left it open.
      return localStorage.getItem(FILES_PANEL_COLLAPSED_STORAGE_KEY) !== '0'
    } catch {
      return true
    }
  })
  const [threadMenuOpenId, setThreadMenuOpenId] = useState<string | null>(null)
  const [collapsedSidebarSections, setCollapsedSidebarSections] = useState<
    Record<string, boolean>
  >(() => readCollapsedSidebarSections())
  const [openTabsByProject, setOpenTabsByProject] = useState<
    Record<string, string[]>
  >(() => readOpenTabsByProject())
  const [workspaceVersion, setWorkspaceVersion] = useState(0)
  const [workspaceFiles, setWorkspaceFiles] = useState<WorkspaceFile[]>([])
  /** Materialized session used for Files/@ mentions while the route stays on /agents/new. */
  const [draftWorkspaceSessionId, setDraftWorkspaceSessionId] = useState<
    string | null
  >(null)
  const [integrationValues, setIntegrationValues] = useState<
    Record<string, string>
  >({})
  const sessionIdRef = useRef<string | null>(null)

  return {
    connectionLimitDismissed,
    setConnectionLimitDismissed,
    newProjectOpen,
    setNewProjectOpen,
    projectSettingsOpen,
    setProjectSettingsOpen,
    projectScopeId,
    setProjectScopeId,
    lastSessionByScope,
    setLastSessionByScope,
    recentProjectIds,
    setRecentProjectIds,
    skillDetail,
    setSkillDetail,
    globalSearchOpen,
    setGlobalSearchOpen,
    pendingOpenPath,
    setPendingOpenPath,
    pendingMentionRef,
    pendingAttachmentsRef,
    sidebarPanelRef,
    filesPanelRef,
    copiedMessageId,
    setCopiedMessageId,
    copiedResumeCommand,
    setCopiedResumeCommand,
    cliMenuOpen,
    setCliMenuOpen,
    terminalOpen,
    setTerminalOpen,
    sidebarCollapsed,
    setSidebarCollapsed,
    filesPanelCollapsed,
    setFilesPanelCollapsed,
    threadMenuOpenId,
    setThreadMenuOpenId,
    collapsedSidebarSections,
    setCollapsedSidebarSections,
    openTabsByProject,
    setOpenTabsByProject,
    workspaceVersion,
    setWorkspaceVersion,
    workspaceFiles,
    setWorkspaceFiles,
    draftWorkspaceSessionId,
    setDraftWorkspaceSessionId,
    integrationValues,
    setIntegrationValues,
    sessionIdRef
  }
}
