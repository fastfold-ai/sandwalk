import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Archive,
  CircleX,
  Download,
  Folder,
  MoreVertical,
  Search,
  Terminal,
  Trash2,
  X
} from 'lucide-react'
import { useState } from 'react'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { copyText } from '@/lib/clipboard'
import { cn } from '@/lib/utils'

import { SessionStatusIcon } from './SessionStatusIcon'
import { useSessionTabColors } from './session-tab-colors'
import { TabInlineColorRow } from './tab-context-menu'

/**
 * Header por panel dentro del split view.
 *
 * Reemplaza los botones flotantes del `SessionMainHeader` cuando el chat
 * vive dentro de un grupo — así cada panel tiene su propio "centro de
 * mando" y las acciones nunca son ambiguas sobre a qué chat aplican.
 *
 *  - Izquierda arriba: status icon + color dot + título del chat.
 *  - Izquierda abajo:  link tipo carpeta con el nombre del proyecto.
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
  // Toggles compartidos con el shell — apuntan al panel único global
  // (Files / Terminal / Preview). Se van a mover a modal en otra iteración.
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
  onInspect?: (session: AgentSession) => void
  onArchive?: (session: AgentSession) => void | Promise<void>
  onClose?: (sessionId: string) => void
  onCloseOthers?: (sessionId: string) => void
  onDelete?: (session: AgentSession) => void
}

export function ChatSplitPanelHeader({
  session,
  focused,
  onFocusPanel,
  projects,
  onSelectProjectScope,
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
  onInspect,
  onArchive,
  onClose,
  onCloseOthers,
  onDelete
}: ChatSplitPanelHeaderProps) {
  const { tabColors, setTabColor } = useSessionTabColors()
  const [cliOpen, setCliOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [colorOpen, setColorOpen] = useState(false)

  const title = session?.title || 'Untitled'
  const project = session?.projectId
    ? projects.find(p => p.id === session.projectId) || null
    : null
  const color = session ? tabColors[session.id] ?? null : null

  const withFocus = (fn: () => void) => () => {
    if (!focused) onFocusPanel()
    fn()
  }

  return (
    <div
      className={cn(
        'flex h-10 shrink-0 items-center gap-2 border-b px-3 text-[12px] transition-colors',
        focused
          ? 'bg-muted/60 border-border/60 text-foreground'
          : 'bg-muted/25 border-border/30 text-muted-foreground'
      )}
    >
      {/* Izquierda: status + color + título / proyecto */}
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
        <div className="flex min-w-0 flex-1 flex-col leading-tight">
          <span
            className={cn(
              'truncate text-[13px]',
              focused ? 'font-medium' : 'font-normal'
            )}
          >
            {title}
          </span>
          {project ? (
            <button
              type="button"
              onClick={() => onSelectProjectScope(project.id)}
              className="text-muted-foreground hover:text-foreground -ml-0.5 mt-0.5 inline-flex w-fit max-w-full items-center gap-1 truncate rounded-sm text-[11px] transition-colors"
              title={project.name}
            >
              <Folder className="size-3 shrink-0" aria-hidden />
              <span className="truncate">{project.name}</span>
            </button>
          ) : null}
        </div>
      </div>

      {/* Derecha: acciones + ellipsis */}
      <TooltipProvider delayDuration={300}>
        <div className="flex shrink-0 items-center gap-0.5">
          {showFiles ? (
            <IconBtn
              label={filesPanelCollapsed ? 'Show files' : 'Hide files'}
              active={!filesPanelCollapsed && panelView === 'files'}
              onClick={withFocus(onToggleFiles)}
            >
              <FilesIcon />
            </IconBtn>
          ) : null}
          {showPreview ? (
            <IconBtn
              label="Site preview"
              active={panelView === 'preview' && !filesPanelCollapsed}
              onClick={withFocus(onOpenPreview)}
            >
              <PreviewIcon />
            </IconBtn>
          ) : null}
          {showTerminal ? (
            <IconBtn
              label={terminalOpen ? 'Hide terminal' : 'Show terminal'}
              active={terminalOpen}
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
            <DropdownMenu>
              <Tooltip>
                <TooltipTrigger asChild>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      className="inline-flex size-7 items-center justify-center rounded-md hover:bg-black/[0.06] dark:hover:bg-white/[0.08]"
                      aria-label="More actions"
                    >
                      <MoreVertical className="size-3.5" />
                    </button>
                  </DropdownMenuTrigger>
                </TooltipTrigger>
                <TooltipContent side="bottom">More</TooltipContent>
              </Tooltip>
              <DropdownMenuContent
                align="end"
                sideOffset={6}
                className="w-56 p-1"
                onCloseAutoFocus={event => event.preventDefault()}
              >
                <DropdownMenu open={colorOpen} onOpenChange={setColorOpen}>
                  <div className="px-2 py-1.5">
                    <div className="text-muted-foreground mb-1 text-[10px] font-semibold uppercase tracking-wide">
                      Color
                    </div>
                    <TabInlineColorRow
                      value={color}
                      onSelect={value => setTabColor(session.id, value)}
                      onClear={() => setTabColor(session.id, null)}
                    />
                  </div>
                </DropdownMenu>
                <DropdownMenuSeparator />
                {onExport ? (
                  <DropdownMenuItem
                    className="gap-2 text-[13px]"
                    onSelect={() => void onExport(session)}
                  >
                    <Download className="size-3.5" />
                    Export session
                  </DropdownMenuItem>
                ) : null}
                {onInspect ? (
                  <DropdownMenuItem
                    className="gap-2 text-[13px]"
                    onSelect={() => onInspect(session)}
                  >
                    <Search className="size-3.5" />
                    Inspect chat
                  </DropdownMenuItem>
                ) : null}
                {onArchive ? (
                  <DropdownMenuItem
                    className="gap-2 text-[13px]"
                    onSelect={() => void onArchive(session)}
                  >
                    <Archive className="size-3.5" />
                    {session.organizeLabel === 'archive'
                      ? 'Unarchive'
                      : 'Archive'}
                  </DropdownMenuItem>
                ) : null}
                <DropdownMenuSeparator />
                {onClose ? (
                  <DropdownMenuItem
                    className="gap-2 text-[13px]"
                    onSelect={() => onClose(session.id)}
                  >
                    <X className="size-3.5" />
                    Close
                  </DropdownMenuItem>
                ) : null}
                {onCloseOthers ? (
                  <DropdownMenuItem
                    className="gap-2 text-[13px]"
                    onSelect={() => onCloseOthers(session.id)}
                  >
                    <CircleX className="size-3.5" />
                    Close others
                  </DropdownMenuItem>
                ) : null}
                {onDelete ? (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive gap-2 text-[13px]"
                      onSelect={() => onDelete(session)}
                    >
                      <Trash2 className="size-3.5" />
                      Delete
                    </DropdownMenuItem>
                  </>
                ) : null}
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
        </div>
      </TooltipProvider>
    </div>
  )
}

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

function PreviewIcon() {
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
      <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}
