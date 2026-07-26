import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Check,
  Copy,
  Download,
  Folder,
  PanelRight,
  SquareTerminal,
  Terminal
} from 'lucide-react'
import type { Dispatch, SetStateAction } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { DesktopDragRegion } from '@/components/DesktopDragRegion'
import { SessionTabs } from '@/components/agents/SessionTabs'
import {
  SHELL_SIDEBAR_MOTION_MS,
  ShellNavControlsSlot
} from '@/components/ShellNavStrip'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { useCrossfadeFlag } from '@/hooks/useDeferredTrue'
import { useMacDesktopOverlay } from '@/hooks/useMacDesktopOverlay'
import { copyText } from '@/lib/clipboard'
import { cn } from '@/lib/utils'

export type SessionMainHeaderProps = {
  sidebarCollapsed: boolean
  setSidebarCollapsed: Dispatch<SetStateAction<boolean>>
  openTabs: AgentSession[]
  sessionId: string | null
  session: AgentSession | null
  navigate: NavigateFunction
  openSessionTab: (sessionId: string) => void
  prefetchSessionMessages: (sessionId: string) => void | Promise<void>
  closeSessionTab: (sessionId: string) => void
  closeOtherSessionTabs: (sessionId: string) => void
  openRenameDialog: (target: AgentSession) => void
  updateSession: (
    target: AgentSession,
    changes: Parameters<LocalAgentClient['updateSession']>[1]
  ) => void | Promise<void>
  exportTranscript: (target: AgentSession) => void | Promise<void>
  setDeleteTarget: Dispatch<SetStateAction<AgentSession | null>>
  projects: AgentProject[]
  selectProjectScope: (projectId: string) => void
  cliMenuOpen: boolean
  setCliMenuOpen: Dispatch<SetStateAction<boolean>>
  copiedResumeCommand: boolean
  setCopiedResumeCommand: Dispatch<SetStateAction<boolean>>
  terminalOpen: boolean
  setTerminalOpen: Dispatch<SetStateAction<boolean>>
  filesPanelCollapsed: boolean
  setFilesPanelCollapsed: Dispatch<SetStateAction<boolean>>
}

export function SessionMainHeader({
  sidebarCollapsed,
  setSidebarCollapsed,
  openTabs,
  sessionId,
  session,
  navigate,
  openSessionTab,
  prefetchSessionMessages,
  closeSessionTab,
  closeOtherSessionTabs,
  openRenameDialog,
  updateSession,
  exportTranscript,
  setDeleteTarget,
  projects,
  selectProjectScope,
  cliMenuOpen,
  setCliMenuOpen,
  copiedResumeCommand,
  setCopiedResumeCommand,
  terminalOpen,
  setTerminalOpen,
  filesPanelCollapsed,
  setFilesPanelCollapsed
}: SessionMainHeaderProps) {
  const overlay = useMacDesktopOverlay()
  // Collapse: reveal after panel closes. Expand: keep briefly so icons don't gap.
  const showCollapsedNav = useCrossfadeFlag(
    sidebarCollapsed,
    SHELL_SIDEBAR_MOTION_MS,
    100
  )
  // Collapsed: one chrome row — traffic lights → toggle/arrows → tabs → actions.
  const padForTrafficLights = showCollapsedNav && overlay

  return (
    <DesktopDragRegion
      asTitleBar={padForTrafficLights}
      className={cn(
        'sandwalk-shell-nav-strip relative z-20 flex h-11 shrink-0 items-center gap-1.5 pr-2',
        padForTrafficLights
          ? 'sandwalk-shell-nav-strip-mac'
          : 'px-1.5 md:px-2'
      )}
    >
      <ShellNavControlsSlot
        visible={showCollapsedNav}
        sidebarCollapsed
        onToggleSidebar={() => setSidebarCollapsed(false)}
      />
      <SessionTabs
        tabs={openTabs}
        activeId={sessionId}
        onSelect={id => {
          openSessionTab(id)
          void prefetchSessionMessages(id)
          navigate(`/agents/${id}`)
        }}
        onClose={closeSessionTab}
        onCloseOthers={closeOtherSessionTabs}
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
      />
      <div className="flex h-8 shrink-0 items-center gap-0.5">
        {session?.projectId
          ? (() => {
              const projectName =
                projects.find(p => p.id === session.projectId)
                  ?.name || null
              if (!projectName) return null
              return (
                <button
                  type="button"
                  className="text-muted-foreground hover:text-foreground mr-1 inline-flex max-w-[12rem] items-center gap-1.5 rounded-md px-1.5 py-1 text-xs"
                  title={projectName}
                  onClick={() =>
                    selectProjectScope(session.projectId!)
                  }
                >
                  <Folder className="size-3.5 shrink-0" />
                  <span className="truncate">{projectName}</span>
                </button>
              )
            })()
          : null}
        <DropdownMenu
          open={cliMenuOpen}
          onOpenChange={open => {
            setCliMenuOpen(open)
            if (!open) setCopiedResumeCommand(false)
          }}
        >
          <DropdownMenuTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8"
              aria-label="Resume in Agent CLI"
              title="Resume in Agent CLI"
              disabled={!sessionId}
            >
              <Terminal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
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
                  {sessionId
                    ? `sandwalk --resume ${sessionId}`
                    : 'sandwalk --resume <chat_id>'}
                </code>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="size-7 shrink-0 rounded-md"
                  disabled={!sessionId}
                  onClick={event => {
                    event.preventDefault()
                    event.stopPropagation()
                    if (!sessionId) return
                    void copyText(
                      `sandwalk --resume ${sessionId}`
                    )
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
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8"
          disabled={!sessionId}
          onClick={() => {
            if (terminalOpen) {
              setTerminalOpen(false)
              return
            }
            setFilesPanelCollapsed(false)
            setTerminalOpen(true)
          }}
          aria-label={
            terminalOpen ? 'Hide terminal' : 'Show terminal'
          }
          title={terminalOpen ? 'Hide terminal' : 'Show terminal'}
        >
          <SquareTerminal
            className={cn(
              'size-4',
              terminalOpen && 'text-foreground'
            )}
          />
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={() =>
            setFilesPanelCollapsed(current => !current)
          }
          aria-label={
            filesPanelCollapsed
              ? 'Show files panel'
              : 'Hide files panel'
          }
          title={
            filesPanelCollapsed
              ? 'Show files panel'
              : 'Hide files panel'
          }
        >
          <PanelRight
            className={cn(
              'size-4',
              !filesPanelCollapsed && 'text-foreground'
            )}
          />
        </Button>
      </div>
    </DesktopDragRegion>
  )
}
