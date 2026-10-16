import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Archive,
  Download,
  Folder,
  Globe2,
  MoreVertical,
  Pencil,
  Search,
  Terminal,
  X
} from 'lucide-react'
import { memo, useState } from 'react'

import { ContinueInSubmenu } from '@/components/agents/ExternalAgentMenuBlocks'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import { SplitMenuBlock } from '@/components/agents/split-menu'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { copyText } from '@/lib/clipboard'
import type { PaneSplitDirection, PaneSplitTarget } from '@/lib/pane-split'
import { perfCount } from '@/lib/perf-probe'
import { cn } from '@/lib/utils'

import { useSessionTabColors } from './session-tab-colors'
import { SessionStatusIcon } from './SessionStatusIcon'
import {
  TabContextItem,
  TabContextSeparator,
  TabInlineColorRow
} from './tab-context-menu'

/**
 * Header por panel dentro del split view.
 *
 * Reemplaza los botones flotantes del `SessionMainHeader` cuando el chat
 * vive dentro de un grupo — así cada panel tiene su propio "centro de
 * mando" y las acciones nunca son ambiguas sobre a qué chat aplican.
 *
 *  - Izquierda: status icon + color dot + título del chat. (El chip del
 *    proyecto se quitó: solo ocupaba espacio; el proyecto vive en el
 *    sidebar y en "Move to project…".)
 *  - Derecha: files / terminal / preview / resume CLI + ellipsis con
 *    las opciones del context menu del tab (sin Pin, sin Split-with —
 *    no aplican dentro del grupo).
 *
 *  Cuando el panel no está focused el header se pinta apagado. Todos los
 *  botones (excepto los del ellipsis, que abren un popover) hacen
 *  `onFocusPanel` antes de disparar su acción para que la vista global
 *  (Files / Terminal / Preview) siempre abra apuntando al chat sobre el
 *  que se clickeó.
 */

export type ChatSplitPanelHeaderProps = {
  session: AgentSession | null
  focused: boolean
  onFocusPanel: () => void
  projects: AgentProject[]
  onSelectProjectScope: (projectId: string) => void
  // Toggles shared with the shell — they point at the single global
  // panel (Files / Terminal / Preview). To be moved into a modal in a
  // future iteration.
  showFiles: boolean
  showTerminal: boolean
  showPreview: boolean
  filesPanelCollapsed: boolean
  terminalOpen: boolean
  panelView: 'files' | 'preview'
  onToggleFiles: () => void
  onToggleTerminal: () => void
  onOpenPreview: () => void
  // CLI resume + export
  showCli: boolean
  onExport?: (session: AgentSession) => void | Promise<void>
  // Ellipsis
  onRename?: (session: AgentSession) => void
  onInspect?: (session: AgentSession) => void
  onArchive?: (session: AgentSession) => void | Promise<void>
  /**
   * Sacar el chat del split — no borra el chat, solo lo quita del
   * grupo. El chat vuelve a estar suelto en su proyecto. Si el grupo
   * queda con menos de 2 chats después, se auto-disuelve.
   */
  onRemoveFromSplit?: (sessionId: string) => void
  onDelete?: (session: AgentSession) => void
  /**
   * Reasignar el chat a otro proyecto (o quitárselo). Mismo comportamiento
   * que "Move to project" del context menu del strip, expuesto también
   * dentro del split para que el usuario pueda mover un chat sin cerrar
   * el grupo primero.
   */
  onMoveToProject?: (
    session: AgentSession,
    projectId: string | null
  ) => void | Promise<void>
  /**
   * Same Split Down / Split Right choices as the tab menu. `Close pane`
   * stays on `onRemoveFromSplit`.
   */
  onSplitPane?: (
    sessionId: string,
    direction: PaneSplitDirection,
    target: PaneSplitTarget
  ) => void
}

function ChatSplitPanelHeaderInner({
  session,
  focused,
  onFocusPanel,
  projects,
  onSelectProjectScope: _onSelectProjectScope,
  showFiles,
  showTerminal,
  showPreview,
  filesPanelCollapsed,
  terminalOpen,
  panelView,
  onToggleFiles,
  onToggleTerminal,
  onOpenPreview,
  showCli,
  onExport,
  onRename,
  onMoveToProject,
  onInspect,
  onArchive,
  onRemoveFromSplit,
  onDelete: _onDelete,
  onSplitPane
}: ChatSplitPanelHeaderProps) {
  perfCount('render.ChatSplitPanelHeader')
  const { tabColors, setTabColor } = useSessionTabColors()
  const [cliOpen, setCliOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  const title = session?.title || 'Untitled'
  const color = session ? tabColors[session.id] ?? null : null

  const closeMenuThen = (fn: () => void) => () => {
    setMenuOpen(false)
    fn()
  }

  const withFocus = (fn: () => void) => () => {
    if (!focused) onFocusPanel()
    fn()
  }

  return (
    <div
      className={cn(
        'flex h-[52px] shrink-0 items-center gap-2 border-b px-3 text-[12px] transition-colors',
        focused
          ? 'bg-muted/60 border-border/60 text-foreground'
          : 'bg-muted/25 border-border/30 text-muted-foreground'
      )}
    >
      {/* Left: status + color + title / project */}
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <span className="flex size-5 shrink-0 items-center justify-center">
          {session ? <SessionStatusIcon status={session.status} /> : null}
        </span>
        {color ? (
          <span
            className="size-2 shrink-0 rounded-full border border-black/10"
            style={{ backgroundColor: color }}
            aria-hidden
          />
        ) : null}
        <span className="min-w-0 flex-1 truncate text-[13px] font-medium">
          {title}
        </span>
      </div>

      {/* Derecha: acciones + ellipsis */}
      <TooltipProvider delayDuration={300}>
        <div className="flex shrink-0 items-center gap-0.5">
          {showFiles ? (
            <IconBtn
              label={
                focused && !filesPanelCollapsed && panelView === 'files'
                  ? 'Hide files'
                  : 'Show files'
              }
              active={focused && !filesPanelCollapsed && panelView === 'files'}
              onClick={withFocus(onToggleFiles)}
            >
              <FilesIcon />
            </IconBtn>
          ) : null}
          {showPreview ? (
            <IconBtn
              label="Site preview"
              active={
                focused && panelView === 'preview' && !filesPanelCollapsed
              }
              onClick={withFocus(onOpenPreview)}
            >
              <Globe2 className="size-3.5" />
            </IconBtn>
          ) : null}
          {showTerminal ? (
            <IconBtn
              label={
                focused && terminalOpen ? 'Hide terminal' : 'Show terminal'
              }
              active={focused && terminalOpen}
              onClick={withFocus(onToggleTerminal)}
            >
              <TerminalIcon />
            </IconBtn>
          ) : null}
          {showCli && session ? (
            <DropdownMenu open={cliOpen} onOpenChange={setCliOpen}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      className={cn(
                        'inline-flex size-7 items-center justify-center rounded-md hover:bg-black/[0.06] dark:hover:bg-white/[0.08]',
                        cliOpen &&
                          'text-foreground bg-black/[0.08] dark:bg-white/[0.1]'
                      )}
                      aria-label="Resume in Agent CLI"
                    >
                      <Terminal className="size-3.5" />
                    </button>
                  </DropdownMenuTrigger>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  Resume in Agent CLI
                </TooltipContent>
              </Tooltip>
              <DropdownMenuContent
                align="end"
                sideOffset={6}
                className="w-[22rem] p-3"
              >
                <p className="text-foreground text-sm font-semibold">
                  Resume in Agent CLI
                </p>
                <div className="border-border/80 bg-muted/35 mt-2 flex items-center gap-2 rounded-lg border p-2">
                  <Terminal className="text-muted-foreground size-4 shrink-0" />
                  <code className="min-w-0 flex-1 truncate font-mono text-[12px]">
                    {`sandwalk --resume ${session.id}`}
                  </code>
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground rounded-md p-1 text-[11px] font-medium"
                    onClick={() => {
                      void copyText(`sandwalk --resume ${session.id}`)
                      setCopied(true)
                      window.setTimeout(() => setCopied(false), 1500)
                    }}
                  >
                    {copied ? 'Copied' : 'Copy'}
                  </button>
                </div>
                {onExport ? (
                  <button
                    type="button"
                    onClick={() => {
                      void onExport(session)
                      setCliOpen(false)
                    }}
                    className="hover:bg-muted mt-2 flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-[13px]"
                  >
                    <Download className="size-3.5" />
                    Export transcript
                  </button>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
          {session ? (
            <Popover open={menuOpen} onOpenChange={setMenuOpen}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      className="inline-flex size-7 items-center justify-center rounded-md hover:bg-black/[0.06] dark:hover:bg-white/[0.08]"
                      aria-label="More actions"
                    >
                      <MoreVertical className="size-3.5" />
                    </button>
                  </PopoverTrigger>
                </TooltipTrigger>
                <TooltipContent side="bottom">More</TooltipContent>
              </Tooltip>
              {/*
                Popover + the tab-context primitives instead of a Radix
                DropdownMenu: its `DropdownMenuSub` flyouts open on
                pointer-move only, which WebKit in the Tauri window drops
                often enough that Split Down/Right looked dead.
              */}
              <PopoverContent
                align="end"
                sideOffset={6}
                className="w-52 p-1.5"
                onCloseAutoFocus={event => event.preventDefault()}
              >
                {onRename ? (
                  <TabContextItem
                    icon={<Pencil />}
                    label="Rename chat…"
                    onClick={closeMenuThen(() => onRename(session))}
                  />
                ) : null}
                {onMoveToProject && projects.length > 0 ? (
                  <ProjectPicker
                    projects={projects}
                    value={session.projectId}
                    noneLabel="No project"
                    trigger={
                      <button
                        type="button"
                        role="menuitem"
                        className="hover:bg-muted flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left text-xs [&_svg]:size-3"
                      >
                        <Folder />
                        <span className="min-w-0 flex-1 truncate">Move to project…</span>
                      </button>
                    }
                    onChange={projectId => {
                      setMenuOpen(false)
                      void onMoveToProject(session, projectId)
                    }}
                  />
                ) : null}
                <TabContextSeparator />
                <div className="text-muted-foreground/80 px-2 pb-0.5 pt-0.5 text-[10px] font-semibold uppercase tracking-wide">
                  Color
                </div>
                <TabInlineColorRow
                  value={color}
                  onSelect={value => {
                    setMenuOpen(false)
                    setTabColor(session.id, value)
                  }}
                  onClear={() => {
                    setMenuOpen(false)
                    setTabColor(session.id, null)
                  }}
                />
                <TabContextSeparator />
                <ContinueInSubmenu session={session} onClose={() => setMenuOpen(false)} />
                {onExport ? (
                  <TabContextItem
                    icon={<Download />}
                    label="Export session"
                    onClick={closeMenuThen(() => void onExport(session))}
                  />
                ) : null}
                {onInspect ? (
                  <TabContextItem
                    icon={<Search />}
                    label="Inspect chat"
                    onClick={closeMenuThen(() => onInspect(session))}
                  />
                ) : null}
                {onArchive ? (
                  <TabContextItem
                    icon={<Archive />}
                    label={
                      session.organizeLabel === 'archive' ? 'Unarchive' : 'Archive'
                    }
                    onClick={closeMenuThen(() => void onArchive(session))}
                  />
                ) : null}
                {onSplitPane ? (
                  <>
                    <TabContextSeparator />
                    <SplitMenuBlock
                      sourceId={session.id}
                      onSplitPane={(id, direction, target) => {
                        setMenuOpen(false)
                        onSplitPane(id, direction, target)
                      }}
                      trailingSeparator={false}
                    />
                  </>
                ) : null}
                {onRemoveFromSplit ? (
                  <>
                    <TabContextSeparator />
                    <TabContextItem
                      icon={<X />}
                      label="Close pane"
                      onClick={closeMenuThen(() => onRemoveFromSplit(session.id))}
                    />
                  </>
                ) : null}
                {/*
                  "Close others" no vive acá — sí existe en la strip
                  global sobre el split entero, pero acá cerrar los
                  "otros" chats del split individualmente no es una
                  operación natural. Si el usuario quiere quedarse con
                  uno solo, mejor disolver el split.

                  Delete tampoco vive acá — es destructivo y fácil
                  confundir con Close en este contexto. La acción existe
                  solo en el sidebar izquierdo, donde el usuario ya está
                  en modo "organizar" y hay
                  menos riesgo de accidente.
                */}
              </PopoverContent>
            </Popover>
          ) : null}
        </div>
      </TooltipProvider>
    </div>
  )
}

/**
 * Memoized: one per pane, re-rendered on every App cascade otherwise. The
 * parent pins its handlers with `useStableHandlers`, so only real changes
 * (session row, focus, panel flags) get through.
 */
export const ChatSplitPanelHeader = memo(ChatSplitPanelHeaderInner)

function IconBtn({
  label,
  active,
  onClick,
  children
}: {
  label: string
  active?: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          data-pane-action=""
          onClick={onClick}
          className={cn(
            'inline-flex size-7 items-center justify-center rounded-md hover:bg-black/[0.06] dark:hover:bg-white/[0.08]',
            active && 'text-foreground bg-black/[0.08] dark:bg-white/[0.1]'
          )}
          aria-label={label}
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom">{label}</TooltipContent>
    </Tooltip>
  )
}

function FilesIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="size-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M4 4h6l2 2h8v12H4z" />
    </svg>
  )
}

function TerminalIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="size-3.5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect width="18" height="18" x="3" y="3" rx="2" />
      <path d="m8 10 2 2-2 2" />
      <path d="M12 14h4" />
    </svg>
  )
}
