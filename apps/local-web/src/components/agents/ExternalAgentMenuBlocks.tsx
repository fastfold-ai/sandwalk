import type {
  AgentSession,
  ExternalAgentKind,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import { ArrowRightLeft, MessageSquare, MessageSquarePlus, SquareTerminal } from 'lucide-react'
import type { PointerEvent, RefObject } from 'react'
import { createPortal } from 'react-dom'

import {
  TabContextItem,
  TabContextSeparator,
  TabContextSubmenu
} from '@/components/agents/tab-context-menu'
import { SandwalkMark } from '@/components/SandwalkMark'
import {
  continueSessionIn,
  continueSessionInSandwalkCli,
  convertTerminalToAgent,
  convertTerminalToSession,
  launchExternalAgent,
  useAgentInstalled,
  useExternalAgentActions
} from '@/lib/external-agent-actions'
import { useTerminalsStore } from '@/lib/terminals-store'

import {
  EXTERNAL_AGENT_KINDS,
  EXTERNAL_AGENT_LABELS,
  ExternalAgentIcon,
  NATIVE_HANDOFF_KINDS
} from './ExternalAgentIcon'




/** Context-menu submenu: Continue in Claude Code / Codex / OpenCode / fx. */
export function ContinueInSubmenu({
  session,
  onClose
}: {
  session: AgentSession
  onClose: () => void
}) {
  const installed = useExternalAgentActions(state => state.installed)
  const busy = useExternalAgentActions(state => Boolean(state.busy[`handoff:${session.id}`]))
  const enabled = (kind: ExternalAgentKind) => installed?.[kind] ?? true
  return (
    <TabContextSubmenu icon={<ArrowRightLeft />} label="Continue in…">
      <TabContextItem
        icon={<SandwalkMark className="size-3.5 shrink-0" />}
        label="Sandwalk CLI"
        disabled={busy}
        trailing={<span className="text-muted-foreground text-[10px]">resume</span>}
        onClick={() => {
          onClose()
          void continueSessionInSandwalkCli(session)
        }}
      />
      <TabContextSeparator />
      {EXTERNAL_AGENT_KINDS.map(kind => (
        <TabContextItem
          key={kind}
          icon={<ExternalAgentIcon kind={kind} />}
          label={EXTERNAL_AGENT_LABELS[kind]}
          disabled={busy || !enabled(kind)}
          trailing={
            !enabled(kind) ? (
              <span className="text-muted-foreground text-[10px]">not installed</span>
            ) : undefined
          }
          onClick={() => {
            onClose()
            void continueSessionIn(session, kind)
          }}
        />
      ))}
      <TabContextSeparator />
      {EXTERNAL_AGENT_KINDS.filter(kind => NATIVE_HANDOFF_KINDS.has(kind)).map(kind => (
        <TabContextItem
          key={`${kind}-native`}
          icon={<ExternalAgentIcon kind={kind} />}
          label={`${EXTERNAL_AGENT_LABELS[kind]} · native history`}
          disabled={busy || !enabled(kind)}
          trailing={<span className="text-muted-foreground text-[10px]">experimental</span>}
          onClick={() => {
            onClose()
            void continueSessionIn(session, kind, { native: true })
          }}
        />
      ))}
    </TabContextSubmenu>
  )
}


const MENU_BUTTON =
  'hover:bg-accent flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-[13px] outline-none disabled:opacity-40'

/**
 * "+" menu. Real buttons, portaled to `document.body`.
 *
 * The tab strip is a window-drag region. A Radix menu item's select
 * event never arrives there, so the row highlights and the terminal
 * is never created. `pointerdown` on a `<button>` runs immediately.
 */
export function NewTabMenu({
  open,
  top,
  right,
  menuRef,
  onCreateSession,
  onCreateTerminal,
  onCreateAgentTerminal
}: {
  open: boolean
  top: number
  right: number
  menuRef: RefObject<HTMLDivElement | null>
  onCreateSession: () => void
  onCreateTerminal?: () => void
  onCreateAgentTerminal?: (kind: ExternalAgentKind | 'sandwalk') => void
}) {
  if (!open || typeof document === 'undefined') return null
  // Fire on pointerdown so a native window drag (the tab strip is a
  // drag region on macOS) cannot swallow the click, and stop the event
  // so the strip's own drag handler never sees it.
  const press = (event: PointerEvent, action: () => void) => {
    if (event.button !== 0) return
    event.preventDefault()
    event.stopPropagation()
    action()
  }
  return createPortal(
    <div
      ref={menuRef}
      data-sandwalk-new-menu
      data-tauri-drag-region="false"
      data-no-window-drag
      role="menu"
      style={{ position: 'fixed', top, right, zIndex: 80 }}
      className="sandwalk-glass-menu bg-popover text-popover-foreground min-w-[180px] rounded-md border p-1 shadow-md"
      onPointerDown={event => event.stopPropagation()}
      onMouseDown={event => event.stopPropagation()}
      onClick={event => event.stopPropagation()}
    >
      <button
        type="button"
        role="menuitem"
        data-tauri-drag-region="false"
        className={MENU_BUTTON}
        onPointerDown={event => press(event, onCreateSession)}
      >
        <MessageSquare className="size-3.5 text-sky-500" />
        New agent chat
      </button>
      {onCreateTerminal ? (
        <button
          type="button"
          role="menuitem"
          data-tauri-drag-region="false"
          className={MENU_BUTTON}
          onPointerDown={event => press(event, onCreateTerminal)}
        >
          <SquareTerminal className="text-muted-foreground/70 size-3.5" />
          New terminal
        </button>
      ) : null}
      {onCreateTerminal ? <div className="bg-border -mx-1 my-1 h-px" /> : null}
      <button
        type="button"
        role="menuitem"
        data-tauri-drag-region="false"
        className={MENU_BUTTON}
        onPointerDown={event =>
          press(event, () => {
            onCreateAgentTerminal?.('sandwalk')
          })
        }
      >
        <SandwalkMark className="size-3.5 shrink-0" />
        <span className="min-w-0 flex-1">Sandwalk CLI</span>
      </button>
      {EXTERNAL_AGENT_KINDS.map(kind => (
        <AgentLaunchButton
          key={kind}
          kind={kind}
          press={press}
          onLaunch={onCreateAgentTerminal}
        />
      ))}
    </div>,
    document.body
  )
}

function AgentLaunchButton({
  kind,
  press,
  onLaunch
}: {
  kind: ExternalAgentKind
  press: (event: PointerEvent, action: () => void) => void
  onLaunch?: (kind: ExternalAgentKind) => void
}) {
  const installed = useAgentInstalled(kind)
  return (
    <button
      type="button"
      role="menuitem"
      disabled={!installed}
      data-tauri-drag-region="false"
      className={MENU_BUTTON}
      onPointerDown={event => {
        if (!installed) return
        press(event, () => {
          if (onLaunch) onLaunch(kind)
          else void launchExternalAgent(kind)
        })
      }}
    >
      <ExternalAgentIcon kind={kind} />
      <span className="min-w-0 flex-1">{EXTERNAL_AGENT_LABELS[kind]}</span>
      {!installed ? (
        <span className="text-muted-foreground text-[10px]">not installed</span>
      ) : null}
    </button>
  )
}

/**
 * Terminal menus: "Convert to…" flyout, shown only while a CLI agent is
 * detected in the terminal. First row imports the CLI session as a Sandwalk
 * chat; the rest re-open it in another CLI (Claude Code → Codex, …) via the
 * imported chat, which stays in the sidebar as the bridge.
 */
export function ConvertTerminalItem({
  terminal,
  onDone
}: {
  terminal: TerminalSession
  onDone?: () => void
}) {
  // Live value from the terminals store (the `agent.changed` PTY event
  // patches it); the prop is a fallback for a freshly launched row.
  const agent = useTerminalsStore(
    state =>
      state.terminals.find(t => t.id === terminal.id)?.agent ?? terminal.agent ?? null
  )
  const busy = useExternalAgentActions(state => Boolean(state.busy[`convert:${terminal.id}`]))
  const installed = useExternalAgentActions(state => state.installed)
  if (!agent) return null
  const enabled = (kind: ExternalAgentKind) => installed?.[kind] ?? true
  const run = (action: () => Promise<unknown>) => {
    onDone?.()
    void action()
  }
  return (
    <TabContextSubmenu icon={<ArrowRightLeft />} label="Convert to…">
      <TabContextItem
        icon={<MessageSquarePlus />}
        label="Sandwalk chat"
        disabled={busy}
        onClick={() => run(() => convertTerminalToSession(terminal, agent))}
      />
      <TabContextSeparator />
      {EXTERNAL_AGENT_KINDS.filter(kind => kind !== agent).map(kind => (
        <TabContextItem
          key={kind}
          icon={<ExternalAgentIcon kind={kind} />}
          label={EXTERNAL_AGENT_LABELS[kind]}
          disabled={busy || !enabled(kind)}
          trailing={
            !enabled(kind) ? (
              <span className="text-muted-foreground text-[10px]">not installed</span>
            ) : undefined
          }
          onClick={() => run(() => convertTerminalToAgent(terminal, agent, kind))}
        />
      ))}
    </TabContextSubmenu>
  )
}
