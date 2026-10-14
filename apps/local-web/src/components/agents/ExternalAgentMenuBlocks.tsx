import type {
  AgentSession,
  ExternalAgentKind,
  TerminalSession
} from '@sandwalk/agent-ui-core'
import { ArrowRightLeft, MessageSquarePlus } from 'lucide-react'

import {
  TabContextItem,
  TabContextSeparator,
  TabContextSubmenu
} from '@/components/agents/tab-context-menu'
import {
  continueSessionIn,
  convertTerminalToSession,
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

/*
 * Two menu styles live in this app: the floating context menu
 * (`TabContextMenuShell` + `TabContextItem`, tiny text) and the ⋯ popover
 * (`SessionActionsMenu`, plain buttons). Each block below ships both.
 */

const ROW =
  'hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm disabled:opacity-40'

function AgentRowLabel({ kind, native }: { kind: ExternalAgentKind; native?: boolean }) {
  const installed = useAgentInstalled(kind)
  return (
    <>
      <span className="min-w-0 flex-1 truncate">
        {EXTERNAL_AGENT_LABELS[kind]}
        {native ? ' · native history' : ''}
      </span>
      {!installed ? (
        <span className="text-muted-foreground text-[10px]">not installed</span>
      ) : native ? (
        <span className="text-muted-foreground text-[10px]">experimental</span>
      ) : null}
    </>
  )
}

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

/** ⋯ popover rows: Continue in … (one row per CLI, native rows after). */
export function ContinueInRows({
  session,
  onDone
}: {
  session: AgentSession
  onDone?: () => void
}) {
  const busy = useExternalAgentActions(state => Boolean(state.busy[`handoff:${session.id}`]))
  const installed = useExternalAgentActions(state => state.installed)
  const enabled = (kind: ExternalAgentKind) => installed?.[kind] ?? true
  return (
    <>
      <div className="text-muted-foreground/80 px-2 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-wide">
        Continue in
      </div>
      {EXTERNAL_AGENT_KINDS.map(kind => (
        <button
          key={kind}
          type="button"
          className={ROW}
          disabled={busy || !enabled(kind)}
          onClick={() => {
            onDone?.()
            void continueSessionIn(session, kind)
          }}
        >
          <ExternalAgentIcon kind={kind} className="h-3.5 w-3.5" />
          <AgentRowLabel kind={kind} />
        </button>
      ))}
      {EXTERNAL_AGENT_KINDS.filter(kind => NATIVE_HANDOFF_KINDS.has(kind)).map(kind => (
        <button
          key={`${kind}-native`}
          type="button"
          className={ROW}
          disabled={busy || !enabled(kind)}
          onClick={() => {
            onDone?.()
            void continueSessionIn(session, kind, { native: true })
          }}
        >
          <ExternalAgentIcon kind={kind} className="h-3.5 w-3.5" />
          <AgentRowLabel kind={kind} native />
        </button>
      ))}
    </>
  )
}

/** Terminal menus: Convert to Sandwalk session (only while an agent is detected). */
export function ConvertTerminalItem({
  terminal,
  variant,
  onDone
}: {
  terminal: TerminalSession
  variant: 'context' | 'popover'
  onDone?: () => void
}) {
  // Live value from the terminals store (the `agent.changed` PTY event
  // patches it); the prop is a fallback for a freshly launched row.
  const agent = useTerminalsStore(
    state =>
      state.terminals.find(t => t.id === terminal.id)?.agent ?? terminal.agent ?? null
  )
  const busy = useExternalAgentActions(state => Boolean(state.busy[`convert:${terminal.id}`]))
  if (!agent) return null
  const label = `Convert to chat (${EXTERNAL_AGENT_LABELS[agent]})`
  const run = () => {
    onDone?.()
    void convertTerminalToSession(terminal, agent)
  }
  if (variant === 'context') {
    return (
      <TabContextItem
        icon={<MessageSquarePlus />}
        label={label}
        disabled={busy}
        onClick={run}
      />
    )
  }
  return (
    <button type="button" className={ROW} disabled={busy} onClick={run}>
      <MessageSquarePlus className="h-3.5 w-3.5" />
      {label}
    </button>
  )
}
