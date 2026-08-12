import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Check,
  Copy,
  Download,
  Files,
  Folder,
  Globe2,
  Terminal
} from 'lucide-react'
import { useEffect, useRef, type Dispatch, type SetStateAction } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { SessionTabs } from '@/components/agents/SessionTabs'
import { DesktopDragRegion } from '@/components/DesktopDragRegion'
import {
  SHELL_SIDEBAR_MOTION_MS,
  ShellNavControlsSlot
} from '@/components/ShellNavStrip'
import { Button } from '@/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { useCrossfadeFlag } from '@/hooks/useDeferredTrue'
import { useMacDesktopOverlay } from '@/hooks/useMacDesktopOverlay'
import { copyText } from '@/lib/clipboard'
import { isDraftAgentSessionId } from '@/lib/draft-agent'
import { navigateToSession } from '@/lib/navigate-session'
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
  groups?: import('@sandwalk/agent-ui-core').SessionGroup[]
  onSplitWith?: (sourceId: string) => void
  onDissolveGroup?: (groupId: string) => void
  /**
   * Cuando la ruta activa apunta a un grupo, el shell oculta su fila de
   * acciones flotantes (folder / files / terminal / preview / CLI): cada
   * panel del split muestra sus propios controles arriba (evita duplicar
   * y quitar la ambigüedad de "a qué chat aplica").
   */
  inSplitGroup?: boolean
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
  cliMenuOpen,
  setCliMenuOpen,
  copiedResumeCommand,
  setCopiedResumeCommand,
  terminalOpen,
  setTerminalOpen,
  filesPanelCollapsed,
  setFilesPanelCollapsed,
  panelView,
  setPanelView,
  onPrepareDraftWorkspace,
  createSession,
  groups,
  onSplitWith,
  onDissolveGroup,
  selectedChatIds,
  onToggleSelectChat,
  onClearSelection,
  onCreateSplitFromSelection,
  inSplitGroup
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
  const activeProject =
    projects.find(project => project.id === activeProjectId) || null
  const inProject = Boolean(activeProjectId)
  const hasProjectFolder = Boolean(activeProject?.folderPath)
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
    if (terminalOpen) {
      setTerminalOpen(false)
      return
    }
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

  const floatBtn =
    'text-muted-foreground hover:bg-background/80 hover:text-foreground inline-flex size-7 shrink-0 items-center justify-center rounded-md bg-background/55 shadow-sm backdrop-blur-md dark:bg-zinc-900/70 dark:hover:bg-zinc-800/90'

  return (
    <div className="relative z-20 flex shrink-0 flex-col">
      {/* Chrome-style tab strip — floor line broken under the active tab */}
      <DesktopDragRegion
        asTitleBar={padForTrafficLights}
        className={cn(
          /* Full-bleed gray strip (beats mac-glass transparent nav rule) */
          'sandwalk-shell-nav-strip sandwalk-session-tab-strip relative z-20 flex items-end gap-0',
          /* Full-width black floor under tabs + overflow slot (same as bottom-bar) */
          '-mb-[2px] after:pointer-events-none after:absolute after:inset-x-0 after:bottom-0 after:z-[1] after:h-[6px] after:bg-background',
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
          activeId={sessionId}
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
          onTogglePin={item =>
            void updateSession(item, {
              organizeLabel:
                item.organizeLabel === 'pinned' ? null : 'pinned'
            })
          }
          onExport={item => void exportTranscript(item)}
          onInspect={item => navigate(`/agents/${item.id}?inspect=1`)}
          onArchive={item =>
            void updateSession(item, {
              organizeLabel:
                item.organizeLabel === 'archive' ? null : 'archive'
            })
          }
          onDelete={item => setDeleteTarget(item)}
          onCreateSession={
            createSession ? () => void createSession(activeProjectId) : undefined
          }
          groups={groups}
          onSplitWith={onSplitWith}
          onDissolveGroup={onDissolveGroup}
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
        <div className="pointer-events-none absolute inset-x-0 top-full z-30 flex h-0 items-start justify-between px-2.5 pt-1.5">
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
          ) : (
            <span />
          )}
          <div className="pointer-events-auto flex items-center gap-0.5">
            {showCliAction ? (
              <DropdownMenu
                open={cliMenuOpen}
                onOpenChange={open => {
                  setCliMenuOpen(open)
                  if (!open) setCopiedResumeCommand(false)
                }}
              >
                <TooltipProvider delayDuration={300}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <DropdownMenuTrigger asChild>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className={cn(floatBtn, 'size-7')}
                          aria-label="Resume in Agent CLI"
                        >
                          <Terminal className="size-4" />
                        </Button>
                      </DropdownMenuTrigger>
                    </TooltipTrigger>
                    <TooltipContent side="bottom">
                      Resume in Agent CLI
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
                <DropdownMenuContent
                  align="end"
                  sideOffset={6}
                  className="w-[22rem] overflow-hidden rounded-xl p-0"
                  onCloseAutoFocus={event => event.preventDefault()}
                >
                  <div className="px-4 pt-3">
                    <p className="text-foreground text-sm font-semibold">
                      Resume in Agent CLI
                    </p>
                  </div>
                  <div className="px-4 pb-3 pt-2">
                    <div className="border-border/80 bg-muted/35 flex items-center gap-2 rounded-lg border p-2.5">
                      <Terminal className="text-muted-foreground size-4 shrink-0" />
                      <code className="min-w-0 flex-1 truncate font-mono text-[13px]">
                        {`sandwalk --resume ${sessionId}`}
                      </code>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="size-7 shrink-0 rounded-md"
                        onClick={event => {
                          event.preventDefault()
                          event.stopPropagation()
                          if (!sessionId) return
                          void copyText(`sandwalk --resume ${sessionId}`)
                          setCopiedResumeCommand(true)
                          window.setTimeout(
                            () => setCopiedResumeCommand(false),
                            2000
                          )
                        }}
                        aria-label="Copy resume command"
                        title="Copy resume command"
                      >
                        {copiedResumeCommand ? (
                          <Check className="size-3.5" />
                        ) : (
                          <Copy className="size-3.5" />
                        )}
                      </Button>
                    </div>
                    <p className="text-muted-foreground mt-2 text-xs">
                      Continue this session in your local sandwalk CLI.
                    </p>
                  </div>
                  <div className="border-border/70 border-t px-4 py-3">
                    <DropdownMenuItem
                      className="h-10 cursor-pointer gap-2 rounded-lg px-3 text-sm"
                      disabled={!session}
                      onSelect={() => {
                        if (!session) return
                        void exportTranscript(session)
                      }}
                    >
                      <Download className="size-4" />
                      Export transcript
                    </DropdownMenuItem>
                  </div>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : null}
            <TooltipProvider delayDuration={300}>
              {showTerminalAction ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className={cn(
                        floatBtn,
                        terminalOpen &&
                          'text-foreground bg-background dark:bg-zinc-800'
                      )}
                      onClick={openTerminal}
                      aria-label={
                        terminalOpen ? 'Hide terminal' : 'Show terminal'
                      }
                    >
                      <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="size-4"
                        aria-hidden
                      >
                        <rect width="18" height="18" x="3" y="3" rx="2" />
                        <path d="m8 10 2 2-2 2" />
                        <path d="M12 14h4" />
                      </svg>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent
                    side="bottom"
                    className="flex items-center gap-2"
                  >
                    <span>
                      {terminalOpen
                        ? 'Hide terminal'
                        : isDraft && !inProject
                          ? 'Open terminal in home'
                          : 'Show terminal'}
                    </span>
                    <kbd className="text-muted-foreground/80 rounded border px-1 text-[10px] tabular-nums">
                      ⌘⇧T
                    </kbd>
                  </TooltipContent>
                </Tooltip>
              ) : null}
              {showFilesAction ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className={cn(
                        floatBtn,
                        !filesPanelCollapsed &&
                          panelView === 'files' &&
                          'text-foreground bg-background dark:bg-zinc-800'
                      )}
                      onClick={toggleFiles}
                      aria-label={
                        filesPanelCollapsed
                          ? 'Show files panel'
                          : 'Hide files panel'
                      }
                    >
                      <Files className="size-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent
                    side="bottom"
                    className="flex items-center gap-2"
                  >
                    <span>
                      {filesPanelCollapsed
                        ? hasProjectFolder
                          ? 'Show project folder'
                          : 'Show files panel'
                        : 'Hide files panel'}
                    </span>
                    <kbd className="text-muted-foreground/80 rounded border px-1 text-[10px] tabular-nums">
                      ⌘⇧E
                    </kbd>
                  </TooltipContent>
                </Tooltip>
              ) : null}
              {showPreviewAction ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className={cn(
                        floatBtn,
                        !filesPanelCollapsed &&
                          panelView === 'preview' &&
                          'text-foreground bg-background dark:bg-zinc-800'
                      )}
                      onClick={togglePreview}
                      aria-label={
                        panelView === 'preview' && !filesPanelCollapsed
                          ? 'Hide site preview'
                          : 'Show site preview'
                      }
                    >
                      <Globe2 className="size-4" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent
                    side="bottom"
                    className="flex items-center gap-2"
                  >
                    <span>
                      {panelView === 'preview' && !filesPanelCollapsed
                        ? 'Hide site preview'
                        : 'Show site preview'}
                    </span>
                    <kbd className="text-muted-foreground/80 rounded border px-1 text-[10px] tabular-nums">
                      ⌘⇧V
                    </kbd>
                  </TooltipContent>
                </Tooltip>
              ) : null}
            </TooltipProvider>
          </div>
        </div>
      ) : null}
    </div>
  )
}
