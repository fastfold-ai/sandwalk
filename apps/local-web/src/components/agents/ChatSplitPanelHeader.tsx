import type { AgentProject, AgentSession } from '@sandwalk/agent-ui-core'
import {
  Archive,
  ChevronDown,
  Download,
  Folder,
  MoreVertical,
  Pencil,
  Search,
  Terminal,
  X
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { ProjectMark } from '@/components/agents/ProjectMark'
import { ProjectPicker } from '@/components/agents/ProjectPicker'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'

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
}

export function ChatSplitPanelHeader({
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
        <div className="flex min-w-0 flex-1 flex-col leading-tight">
          <span className="truncate text-[13px] font-medium">
            {title}
          </span>
          {/* Proyecto: solo lectura + popover en hover con la ficha
              del proyecto. `onSelectProjectScope` queda en la firma por
              compatibilidad con el shell — se limpia cuando iteremos. */}
          <ProjectMetaHover project={project} />
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
                {onRename ? (
                  <DropdownMenuItem
                    className="gap-2 text-[13px]"
                    onSelect={() => onRename(session)}
                  >
                    <Pencil className="size-3.5" />
                    Rename…
                  </DropdownMenuItem>
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
                        className="hover:bg-muted flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-[13px]"
                      >
                        <Folder className="size-3.5" />
                        Move to project…
                      </button>
                    }
                    onChange={projectId => {
                      void onMoveToProject(session, projectId)
                    }}
                  />
                ) : null}
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
                {onRemoveFromSplit ? (
                  <>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="gap-2 text-[13px]"
                      onSelect={() => onRemoveFromSplit(session.id)}
                    >
                      <X className="size-3.5" />
                      Close
                    </DropdownMenuItem>
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
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
        </div>
      </TooltipProvider>
    </div>
  )
}

/**
 * Chip apagado con el proyecto del chat + ficha informativa al hover.
 * Ya no navega: es texto de contexto puro. El hover abre una ficha
 * organizada por secciones (nombre + icono al tope, luego descripción,
 * carpeta local, contexto del agente, y metadata en el pie). Las
 * secciones vacías desaparecen — solo se muestra lo que el proyecto
 * tiene configurado. Cuando el chat no tiene proyecto asociado, se
 * muestra un fallback discreto con su propia explicación.
 */
function ProjectMetaHover({ project }: { project: AgentProject | null }) {
  /*
   * Popover con hover-para-abrir + click-para-pinnear.
   *
   * Comportamiento:
   *   - Hover sobre el chip abre la ficha con 300 ms de delay.
   *   - Sacar el mouse sin interactuar cierra con 120 ms de delay.
   *   - Cualquier click DENTRO del popover (Ver más/menos, botones, etc.)
   *     lo pinnea: a partir de ahí ya no cierra por hover leave.
   *   - Solo cierra por click fuera (onPointerDownOutside del Popover),
   *     lo cual también resetea el pin.
   *
   * `HoverCard` no servía porque cerraba al colapsar el contenido
   * (mouse queda fuera del popover recién achicado). Este patrón es el
   * mismo que usa GitHub con las user cards y Linear con los previews.
   */
  const [open, setOpen] = useState(false)
  const [pinned, setPinned] = useState(false)
  const openTimerRef = useRef<number | null>(null)
  const closeTimerRef = useRef<number | null>(null)

  const clearTimers = () => {
    if (openTimerRef.current != null) {
      window.clearTimeout(openTimerRef.current)
      openTimerRef.current = null
    }
    if (closeTimerRef.current != null) {
      window.clearTimeout(closeTimerRef.current)
      closeTimerRef.current = null
    }
  }
  useEffect(() => () => clearTimers(), [])

  const scheduleOpen = () => {
    clearTimers()
    openTimerRef.current = window.setTimeout(() => setOpen(true), 300)
  }
  const scheduleClose = () => {
    if (pinned) return
    clearTimers()
    closeTimerRef.current = window.setTimeout(() => setOpen(false), 120)
  }
  const cancelClose = () => {
    if (closeTimerRef.current != null) {
      window.clearTimeout(closeTimerRef.current)
      closeTimerRef.current = null
    }
  }

  return (
    <Popover
      open={open}
      onOpenChange={next => {
        if (!next) {
          setOpen(false)
          setPinned(false)
        } else {
          setOpen(true)
        }
      }}
    >
      <PopoverTrigger asChild>
        {project ? (
          <span
            className="text-muted-foreground hover:text-foreground -mx-1 mt-0.5 inline-flex w-fit max-w-full cursor-default items-center gap-1.5 truncate rounded-md px-1 py-0.5 text-[11px] transition-colors hover:bg-black/[0.05] dark:hover:bg-white/[0.06]"
            onMouseEnter={scheduleOpen}
            onMouseLeave={scheduleClose}
          >
            <ProjectMark
              icon={project.icon}
              color={project.color}
              className="size-4"
              iconClassName="size-2.5"
            />
            <span className="truncate">{project.name}</span>
          </span>
        ) : (
          <span
            className="text-muted-foreground/70 hover:text-muted-foreground -mx-1 mt-0.5 inline-flex w-fit max-w-full cursor-default items-center gap-1 rounded-md px-1 py-0.5 text-[11px] italic transition-colors hover:bg-black/[0.05] dark:hover:bg-white/[0.06]"
            onMouseEnter={scheduleOpen}
            onMouseLeave={scheduleClose}
          >
            Sin proyecto asociado
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent
        side="bottom"
        align="start"
        sideOffset={8}
        className="bg-popover text-popover-foreground flex max-h-[480px] w-[340px] max-w-[92vw] flex-col overflow-hidden rounded-xl border p-0 shadow-lg"
        onOpenAutoFocus={event => event.preventDefault()}
        onMouseEnter={cancelClose}
        onMouseLeave={scheduleClose}
        onClick={() => setPinned(true)}
      >
        {project ? (
          <ProjectFicha project={project} />
        ) : (
          <NoProjectFicha />
        )}
      </PopoverContent>
    </Popover>
  )
}

function ProjectFicha({ project }: { project: AgentProject }) {
  /*
   * Layout de 3 zonas:
   *   - Header fijo arriba (icono + nombre, hasta 3 líneas).
   *   - Zona central con `overflow-y-auto` — todas las secciones scrollean
   *     juntas si la ficha excede los 480px del popover.
   *   - Footer fijo abajo (metadata en muted). Nunca se pierde al scrollear.
   * Descripción y contexto se colapsan a 3 líneas por default con "Ver más".
   */
  return (
    <>
      {/* Header fijo */}
      <div className="flex shrink-0 items-start gap-3 p-4">
        <ProjectMark
          icon={project.icon}
          color={project.color}
          className="size-10 shrink-0"
          iconClassName="size-4"
        />
        <div className="min-w-0 flex-1">
          <h3 className="text-foreground line-clamp-3 text-[14px] font-semibold leading-snug">
            {project.name}
          </h3>
        </div>
      </div>

      {/* Zona scrolleable */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {project.description ? (
          <FichaSection title="Descripción">
            <CollapsibleText text={project.description} />
          </FichaSection>
        ) : null}

        {project.folderPath ? (
          <FichaSection title="Carpeta local">
            <p
              className="text-foreground/90 break-all font-mono text-[11.5px] leading-relaxed"
              title={project.folderPath}
            >
              {project.folderPath}
            </p>
          </FichaSection>
        ) : null}

        {project.agentContext ? (
          <FichaSection title="Contexto para el agente">
            <CollapsibleText text={project.agentContext} />
          </FichaSection>
        ) : null}
      </div>

      {/* Footer fijo */}
      <div className="border-border/60 text-muted-foreground/80 shrink-0 border-t px-4 py-2.5 text-[11px]">
        {formatSessionCount(project.sessionCount)}
        {project.createdAt ? (
          <>
            {' · creado '}
            {formatCreatedAt(project.createdAt)}
          </>
        ) : null}
      </div>
    </>
  )
}

/**
 * Bloque de texto colapsable a 3 líneas con toggle "Ver más / Ver menos".
 * El toggle solo aparece cuando el texto realmente pasa de 3 líneas —
 * comparamos `scrollHeight` vs `clientHeight` en modo colapsado con un
 * ResizeObserver por si el ancho del popover cambia.
 */
function CollapsibleText({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false)
  const [overflows, setOverflows] = useState(false)
  const ref = useRef<HTMLParagraphElement | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const measure = () => {
      if (expanded) return
      setOverflows(el.scrollHeight - el.clientHeight > 1)
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(measure)
    ro.observe(el)
    return () => ro.disconnect()
  }, [text, expanded])

  return (
    <div>
      <p
        ref={ref}
        className={cn(
          'text-foreground/90 whitespace-pre-wrap text-[12px] leading-relaxed',
          !expanded && 'line-clamp-3'
        )}
      >
        {text}
      </p>
      {overflows || expanded ? (
        <button
          type="button"
          onClick={() => setExpanded(v => !v)}
          className="text-muted-foreground hover:text-foreground mt-1 inline-flex items-center gap-1 text-[11px] font-medium"
        >
          {expanded ? (
            <>
              <ChevronDown className="size-3 rotate-180" aria-hidden />
              Ver menos
            </>
          ) : (
            <>
              <ChevronDown className="-rotate-90 size-3" aria-hidden />
              Ver más
            </>
          )}
        </button>
      ) : null}
    </div>
  )
}

function NoProjectFicha() {
  return (
    <div className="flex items-start gap-3 p-4">
      <span className="bg-muted text-muted-foreground inline-flex size-10 shrink-0 items-center justify-center rounded-md">
        <Folder className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="text-foreground text-[13px] font-semibold">
          Sin proyecto asociado
        </h3>
        <p className="text-muted-foreground mt-1 text-[12px] leading-relaxed">
          Este chat no está vinculado a ningún proyecto. Podés asociarlo
          desde el selector de proyecto del composer.
        </p>
      </div>
    </div>
  )
}

function FichaSection({
  title,
  children
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <div className="border-border/60 border-t px-4 py-3">
      <div className="text-muted-foreground mb-1.5 text-[10px] font-semibold uppercase tracking-wider">
        {title}
      </div>
      {children}
    </div>
  )
}

function formatSessionCount(count: number): string {
  if (count === 0) return 'Sin chats'
  if (count === 1) return '1 chat'
  return `${count} chats`
}

function formatCreatedAt(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('es-ES', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })
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
