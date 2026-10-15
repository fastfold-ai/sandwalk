import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  AgentSession,
  SessionGroup
} from '@sandwalk/agent-ui-core'
import {
  Folder
} from 'lucide-react'
import { type Dispatch, type SetStateAction,useEffect, useRef } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { SessionTabs } from '@/components/agents/SessionTabs'
import { DesktopDragRegion } from '@/components/DesktopDragRegion'
import {
  SHELL_SIDEBAR_MOTION_MS,
  ShellNavControlsSlot
} from '@/components/ShellNavStrip'
import { useCrossfadeFlag } from '@/hooks/useDeferredTrue'
import { useMacDesktopOverlay } from '@/hooks/useMacDesktopOverlay'
import { isDraftAgentSessionId } from '@/lib/draft-agent'
import { navigateToSession } from '@/lib/navigate-session'
import type { PaneSplitDirection, PaneSplitTarget } from '@/lib/pane-split'
import { cn } from '@/lib/utils'

export type SessionMainHeaderProps = {
  sidebarCollapsed: boolean
  setSidebarCollapsed: Dispatch<SetStateAction<boolean>>
  openTabs: AgentSession[]
  /** Mezcla real de IDs de sesión y grupo en el orden de la strip. */
  openTabIds?: string[]
  sessionId: string | null
  session: AgentSession | null
  navigate: NavigateFunction
  openSessionTab: (sessionId: string) => void
  prefetchSessionMessages: (sessionId: string) => void | Promise<void>
  closeSessionTab: (sessionId: string) => void
  closeOtherSessionTabs: (sessionId: string) => void
  reorderSessionTabs: (orderedIds: string[]) => void
  openRenameDialog: (target: AgentSession) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  exportTranscript: (target: AgentSession) => void | Promise<void>
  setDeleteTarget: Dispatch<SetStateAction<AgentSession | null>>
  projects: AgentProject[]
  activeProjectId: string | null
  selectProjectScope: (projectId: string) => void
  cliMenuOpen: boolean
  setCliMenuOpen: Dispatch<SetStateAction<boolean>>
  copiedResumeCommand: boolean
  setCopiedResumeCommand: Dispatch<SetStateAction<boolean>>
  terminalOpen: boolean
  setTerminalOpen: Dispatch<SetStateAction<boolean>>
  filesPanelCollapsed: boolean
  setFilesPanelCollapsed: Dispatch<SetStateAction<boolean>>
  panelView: 'files' | 'preview'
  setPanelView: Dispatch<SetStateAction<'files' | 'preview'>>
  onPrepareDraftWorkspace?: () => void | Promise<void>
  /** Opens a fresh draft session (same handler as the sidebar "New agent"). */
  createSession?: (projectId?: string | null) => void | Promise<void>
  /** FAS-107 GF5: create + open a new terminal via the tab-strip "+". */
  onCreateTerminal?: () => void
  /** "+" menu: terminal that starts Claude Code, Codex, OpenCode, or fx. */
  onCreateAgentTerminal?: (
    kind: import('@sandwalk/agent-ui-core').ExternalAgentKind
  ) => void
  /** FAS-107 GF1/GF6: terminals so chips render with type-terminal variant. */
  terminals?: import('@sandwalk/agent-ui-core').TerminalSession[]
  /** FAS-107: close/kill a terminal from its chip. */
  onCloseTerminal?: (terminalId: string) => void
  /** FAS-107 GF-PARITY-5: rename/pin/archive/move a terminal from chip menu. */
  onRenameTerminal?: (terminalId: string) => void
  onToggleTerminalOrganizeLabel?: (
    terminalId: string,
    label: 'pinned' | 'archive'
  ) => void | Promise<void>
  onMoveTerminalToProject?: (
    terminalId: string,
    projectId: string | null
  ) => void | Promise<void>
  groups?: import('@sandwalk/agent-ui-core').SessionGroup[]
  onSplitWith?: (sourceId: string) => void
  onSplitPane?: (
    sourceId: string,
    direction: PaneSplitDirection,
    target: PaneSplitTarget
  ) => void
  onDissolveGroup?: (groupId: string) => void
  onRenameGroup?: (group: SessionGroup) => void
  onSetGroupColor?: (groupId: string, color: string | null) => void
  onSetGroupPinned?: (groupId: string, pinned: boolean) => void
  onArrangeGroup?: (groupId: string, rows: number, cols: number) => void
  onCloseGroup?: (groupId: string) => void
  /**
   * Cuando la ruta activa apunta a un grupo, el shell oculta su fila de
   * acciones flotantes (folder / files / terminal / preview / CLI): cada
   * panel del split muestra sus propios controles arriba (evita duplicar
   * y quitar la ambigüedad de "a qué chat aplica").
   */
  inSplitGroup?: boolean
  /**
   * Id del grupo activo (si el user está en un split). El activeId
   * visual del strip usa `activeGroupId ?? sessionId ?? activeTerminalId`
   * — sin `activeGroupId` un chat que vive oculto dentro de un split
   * nunca resolvería como activo, y sin `activeTerminalId` un terminal
   * suelto en `/terminals/:id` deja su chip apagado.
   */
  activeGroupId?: string | null
  /**
   * FAS-107: id del terminal activo cuando la ruta es `/terminals/:id`.
   * Se usa como último fallback del `activeId` del strip para que el
   * chip del terminal se ilumine igual que un chat activo.
   */
  activeTerminalId?: string | null
  selectedChatIds?: Set<string>
  onToggleSelectChat?: (id: string) => void
  onClearSelection?: () => void
  onCreateSplitFromSelection?: () => void
}

export function SessionMainHeader({
  sidebarCollapsed,
  setSidebarCollapsed,
  openTabs,
  openTabIds,
  sessionId,
  session,
  navigate,
  openSessionTab,
  prefetchSessionMessages,
  closeSessionTab,
  closeOtherSessionTabs,
  reorderSessionTabs,
  openRenameDialog,
  updateSession,
  exportTranscript,
  setDeleteTarget,
  projects,
  activeProjectId,
  selectProjectScope,
  cliMenuOpen: _cliMenuOpen,
  setCliMenuOpen: _setCliMenuOpen,
  copiedResumeCommand: _copiedResumeCommand,
  setCopiedResumeCommand: _setCopiedResumeCommand,
  terminalOpen: _terminalOpen,
  setTerminalOpen,
  filesPanelCollapsed,
  setFilesPanelCollapsed,
  panelView,
  setPanelView,
  onPrepareDraftWorkspace,
  createSession,
  onCreateTerminal,
  onCreateAgentTerminal,
  terminals,
  onCloseTerminal,
  onRenameTerminal,
  onToggleTerminalOrganizeLabel,
  onMoveTerminalToProject,
  groups,
  onSplitWith,
  onSplitPane,
  onDissolveGroup,
  onRenameGroup,
  onSetGroupColor,
  onSetGroupPinned,
  onArrangeGroup,
  onCloseGroup,
  selectedChatIds,
  onToggleSelectChat,
  onClearSelection,
  onCreateSplitFromSelection,
  inSplitGroup,
  activeGroupId,
  activeTerminalId
}: SessionMainHeaderProps) {
  const overlay = useMacDesktopOverlay()
  // Collapse: reveal after panel closes. Expand: keep briefly so icons don't gap.
  const showCollapsedNav = useCrossfadeFlag(
    sidebarCollapsed,
    SHELL_SIDEBAR_MOTION_MS,
    100
  )
  // Collapsed: traffic-light clearance on the tab strip row.
  const padForTrafficLights = showCollapsedNav && overlay
  const isDraft = isDraftAgentSessionId(sessionId)
  const inProject = Boolean(activeProjectId)
  // Draft: host terminal always; Files whenever a project is selected.
  const showTerminalAction = Boolean(sessionId)
  const showCliAction = Boolean(sessionId) && !isDraft
  const showFilesAction = Boolean(sessionId) && (!isDraft || inProject)
  const showPreviewAction = Boolean(sessionId) && !isDraft
  const showFloatingActions =
    showTerminalAction ||
    showCliAction ||
    showFilesAction ||
    showPreviewAction

  const openTerminal = () => {
    // Por ahora la terminal queda siempre abierta y no se puede cerrar.
    // El shortcut ⌘⇧T garantiza que el panel Files se vea (para exponer
    // la terminal si estaba oculto por Files collapsed), pero nunca hace
    // toggle-off — hasta que definamos la UX final.
    if (isDraft && inProject) {
      void (async () => {
        await onPrepareDraftWorkspace?.()
        setFilesPanelCollapsed(false)
        setTerminalOpen(true)
      })()
      return
    }
    if (!isDraft) setFilesPanelCollapsed(false)
    setTerminalOpen(true)
  }

  const toggleFiles = () => {
    if (panelView === 'preview') {
      setPanelView('files')
      setFilesPanelCollapsed(false)
      return
    }
    if (isDraft && inProject && filesPanelCollapsed) {
      void (async () => {
        await onPrepareDraftWorkspace?.()
        setFilesPanelCollapsed(false)
      })()
      return
    }
    setFilesPanelCollapsed(current => !current)
  }

  const togglePreview = () => {
    if (panelView === 'preview' && !filesPanelCollapsed) {
      setFilesPanelCollapsed(true)
      return
    }
    setPanelView('preview')
    setFilesPanelCollapsed(false)
  }

  /*
   * Keyboard shortcuts for the three top-strip toggles.
   * Handlers change on every render (they close over local state); we stash
   * them in a ref that's updated on each render so the effect's listener
   * always calls the latest version without re-registering — that lets the
   * dep array stay honest (just the three visibility flags) and drops the
   * previous eslint-disable.
   */
  const shortcutHandlersRef = useRef({ openTerminal, toggleFiles, togglePreview })
  shortcutHandlersRef.current = { openTerminal, toggleFiles, togglePreview }
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || !event.shiftKey) return
      const key = event.key.toLowerCase()
      if (key === 't' && showTerminalAction) {
        event.preventDefault()
        shortcutHandlersRef.current.openTerminal()
      } else if (key === 'e' && showFilesAction) {
        event.preventDefault()
        shortcutHandlersRef.current.toggleFiles()
      } else if (key === 'v' && showPreviewAction) {
        event.preventDefault()
        shortcutHandlersRef.current.togglePreview()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [showTerminalAction, showFilesAction, showPreviewAction])

  const projectName =
    showCliAction && session?.projectId
      ? projects.find(p => p.id === session.projectId)?.name || null
      : null

  return (
    <div className="relative z-20 flex shrink-0 flex-col">
      {/* Chrome-style tab strip — floor line broken under the active tab */}
      <DesktopDragRegion
        asTitleBar={padForTrafficLights}
        className={cn(
          'sandwalk-shell-nav-strip sandwalk-session-tab-strip relative z-20 flex items-end gap-0',
          padForTrafficLights ? 'sandwalk-shell-nav-strip-mac' : null
        )}
      >
        <ShellNavControlsSlot
          visible={showCollapsedNav}
          sidebarCollapsed
          onToggleSidebar={() => setSidebarCollapsed(false)}
          /* Parent uses items-end (for tabs to sit on the floor); override so
           * the nav buttons align with the tab content vertical center. */
          className="self-center"
        />
        <SessionTabs
          tabs={openTabs}
          openTabIds={openTabIds}
          activeId={activeGroupId ?? sessionId ?? activeTerminalId ?? null}
          onSelect={id => {
            void navigateToSession({
              id,
              openSessionTab,
              prefetchSessionMessages,
              navigate
            })
          }}
          onClose={closeSessionTab}
          onCloseOthers={closeOtherSessionTabs}
          onReorder={reorderSessionTabs}
          onRename={openRenameDialog}
          onTogglePin={item => {
            const willPin = item.organizeLabel !== 'pinned'
            void updateSession(item, {
              organizeLabel: willPin ? 'pinned' : null
            })
            // Al pinear un tab, moverlo al FINAL del cluster de pinneds
            // en el orden del strip. Sin esto, aparecía a la izquierda
            // del cluster de pinneds cuando el `openTabIds` ya lo tenía
            // antes que otros pinneds. Chrome/VSCode ponen el nuevo pin
            // al final del cluster de pinneds.
            if (willPin && openTabIds && openTabs && reorderSessionTabs) {
              const otherPinnedIds = new Set(
                openTabs
                  .filter(
                    tab => tab.organizeLabel === 'pinned' && tab.id !== item.id
                  )
                  .map(tab => tab.id)
              )
              const otherPinnedInStrip = openTabIds.filter(id =>
                otherPinnedIds.has(id)
              )
              const notPinnedInStrip = openTabIds.filter(
                id => !otherPinnedIds.has(id) && id !== item.id
              )
              reorderSessionTabs([
                ...otherPinnedInStrip,
                item.id,
                ...notPinnedInStrip
              ])
            }
          }}
          onExport={item => void exportTranscript(item)}
          onInspect={item => navigate(`/agents/${item.id}?inspect=1`)}
          onArchive={item =>
            void updateSession(item, {
              organizeLabel:
                item.organizeLabel === 'archive' ? null : 'archive'
            })
          }
          onMoveToProject={(item, projectId) =>
            void updateSession(item, { projectId })
          }
          projects={projects}
          onDelete={item => setDeleteTarget(item)}
          onCreateSession={
            createSession ? () => void createSession(activeProjectId) : undefined
          }
          onCreateTerminal={onCreateTerminal}
          onCreateAgentTerminal={onCreateAgentTerminal}
          terminals={terminals}
          onCloseTerminal={onCloseTerminal}
          onRenameTerminal={onRenameTerminal}
          onToggleTerminalOrganizeLabel={onToggleTerminalOrganizeLabel}
          onMoveTerminalToProject={onMoveTerminalToProject}
          groups={groups}
          onSplitWith={onSplitWith}
          onSplitPane={onSplitPane}
          onDissolveGroup={onDissolveGroup}
          onRenameGroup={onRenameGroup}
          onSetGroupColor={onSetGroupColor}
          onSetGroupPinned={onSetGroupPinned}
          onArrangeGroup={onArrangeGroup}
          onCloseGroup={onCloseGroup}
          selectedChatIds={selectedChatIds}
          onToggleSelectChat={onToggleSelectChat}
          onClearSelection={onClearSelection}
          onCreateSplitFromSelection={onCreateSplitFromSelection}
        />
      </DesktopDragRegion>

      {/* Folder + actions float over the session content (no dedicated bar).
          En split view el header de cada panel absorbe estos controles —
          apagamos esta fila para no duplicar y evitar la ambigüedad de
          "cuál chat operan". */}
      {!inSplitGroup && (showFloatingActions || projectName) ? (
        <div className="pointer-events-none absolute inset-x-0 top-full z-30 flex h-0 items-start px-2.5 pt-1.5">
          {projectName && session?.projectId ? (
            <button
              type="button"
              className="pointer-events-auto text-muted-foreground hover:text-foreground inline-flex h-7 max-w-[12rem] items-center gap-1.5 rounded-md bg-background/55 px-2 text-xs shadow-sm backdrop-blur-md dark:bg-zinc-900/70"
              title={projectName}
              onClick={() => selectProjectScope(session.projectId!)}
            >
              <Folder className="size-3.5 shrink-0" />
              <span className="truncate">{projectName}</span>
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
