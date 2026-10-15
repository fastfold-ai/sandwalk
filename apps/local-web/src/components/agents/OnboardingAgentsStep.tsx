import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  ExternalAgentInfo,
  ExternalAgentKind,
  ExternalSessionSummary
} from '@sandwalk/agent-ui-core'
import { Check, Loader } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { cn } from '@/lib/utils'

import {
  EXTERNAL_AGENT_KINDS,
  EXTERNAL_AGENT_LABELS,
  ExternalAgentIcon
} from './ExternalAgentIcon'

const INSTALL_HINT: Record<ExternalAgentKind, string> = {
  claude: 'npm i -g @anthropic-ai/claude-code',
  codex: 'npm i -g @openai/codex',
  opencode: 'curl -fsSL https://opencode.ai/install | bash',
  fx: 'curl -fsSL https://fx.sh/setup.sh | bash',
  hermes: 'curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash'
}

function folderName(cwd: string | null): string {
  if (!cwd) return ''
  const parts = cwd.split('/').filter(Boolean)
  return parts[parts.length - 1] ?? cwd
}

function whenLabel(iso: string | null): string {
  if (!iso) return ''
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return ''
  const days = Math.floor((Date.now() - at.getTime()) / 86_400_000)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days}d ago`
  return at.toLocaleDateString()
}

/**
 * Onboarding → "Your other agents": detect Claude Code / Codex / OpenCode /
 * fx and import recent sessions as Sandwalk chats (history only).
 */
export function OnboardingAgentsStep({ client }: { client: LocalAgentClient }) {
  const [agents, setAgents] = useState<ExternalAgentInfo[] | null>(null)
  const [sessions, setSessions] = useState<ExternalSessionSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<Record<string, boolean>>({})
  const [importing, setImporting] = useState(false)
  const [imported, setImported] = useState<Record<string, boolean>>({})

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    client
      .listExternalAgents({ limit: 30 })
      .then(result => {
        if (cancelled) return
        setAgents(result.agents)
        setSessions(result.sessions)
        setError(null)
      })
      .catch(err => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Could not scan for agent sessions.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [client])

  const installed = useMemo(
    () => new Set((agents ?? []).filter(a => a.installed).map(a => a.kind)),
    [agents]
  )
  const key = (s: ExternalSessionSummary) => `${s.kind}:${s.id}`
  const chosen = sessions.filter(s => selected[key(s)] && !imported[key(s)])

  const importSelected = async () => {
    if (chosen.length === 0 || importing) return
    setImporting(true)
    setError(null)
    const done: Record<string, boolean> = {}
    let failures = 0
    for (const summary of chosen) {
      try {
        await client.importExternalSession({
          kind: summary.kind,
          sessionId: summary.id,
          workspacePath: summary.cwd
        })
        done[key(summary)] = true
      } catch {
        failures += 1
      }
    }
    setImported(prev => ({ ...prev, ...done }))
    setSelected({})
    if (failures) setError(`${failures} session${failures === 1 ? '' : 's'} could not be imported.`)
    setImporting(false)
  }

  if (loading && agents === null) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader className="size-4 animate-spin" />
        Looking for Claude Code, Codex, OpenCode, and fx…
      </p>
    )
  }

  return (
    <div className="space-y-5 pb-2" data-testid="onboarding-agents-step">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {EXTERNAL_AGENT_KINDS.map(kind => {
          const isInstalled = installed.has(kind)
          return (
            <div
              key={kind}
              className={cn(
                'border-border/70 flex items-center gap-2 rounded-lg border px-3 py-2',
                !isInstalled && 'opacity-60'
              )}
              title={isInstalled ? 'Installed' : INSTALL_HINT[kind]}
            >
              <ExternalAgentIcon kind={kind} className="size-4" />
              <span className="min-w-0 flex-1 truncate text-sm">{EXTERNAL_AGENT_LABELS[kind]}</span>
              {isInstalled ? (
                <Check className="size-3.5 text-emerald-600 dark:text-emerald-400" />
              ) : (
                <span className="text-muted-foreground text-[10px]">not found</span>
              )}
            </div>
          )
        })}
      </div>

      {sessions.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          {installed.size === 0
            ? 'None of these CLIs are on this Mac yet. You can import their sessions later from Dashboard, or open them from any terminal tab.'
            : 'No saved sessions found. Once you chat in one of these CLIs, it will show up here and in the terminal menu.'}
        </p>
      ) : (
        <>
          <p className="text-muted-foreground text-xs">
            Pick sessions to bring in as Sandwalk chats. Each keeps its folder as the workspace; the
            transcript is history only until you send a message.
          </p>
          <ul className="border-border/70 divide-border/60 max-h-72 divide-y overflow-y-auto rounded-lg border">
            {sessions.map(summary => {
              const k = key(summary)
              const done = Boolean(imported[k])
              return (
                <li key={k}>
                  <label
                    className={cn(
                      'flex cursor-pointer items-center gap-3 px-3 py-2',
                      done && 'cursor-default opacity-70'
                    )}
                  >
                    <input
                      type="checkbox"
                      className="size-3.5"
                      disabled={done || importing}
                      checked={done || Boolean(selected[k])}
                      onChange={event =>
                        setSelected(prev => ({ ...prev, [k]: event.target.checked }))
                      }
                      aria-label={`Import ${summary.title}`}
                    />
                    <ExternalAgentIcon kind={summary.kind} className="text-muted-foreground size-3.5" />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm">{summary.title}</span>
                      <span className="text-muted-foreground block truncate text-[11px]">
                        {summary.label}
                        {summary.cwd ? ` · ${folderName(summary.cwd)}` : ''}
                        {summary.updatedAt ? ` · ${whenLabel(summary.updatedAt)}` : ''}
                        {` · ${summary.turns} turn${summary.turns === 1 ? '' : 's'}`}
                      </span>
                    </span>
                    {done ? (
                      <span className="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                        <Check className="size-3.5" />
                        Imported
                      </span>
                    ) : null}
                  </label>
                </li>
              )
            })}
          </ul>
          <div className="flex items-center justify-between gap-3">
            <p className="text-muted-foreground text-xs">
              {chosen.length} selected
            </p>
            <button
              type="button"
              disabled={chosen.length === 0 || importing}
              onClick={() => void importSelected()}
              className={cn(
                'bg-foreground text-background inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium transition-opacity disabled:opacity-40',
                importing && 'opacity-60'
              )}
            >
              {importing ? <Loader className="size-4 animate-spin" /> : null}
              Import {chosen.length > 0 ? chosen.length : ''} session{chosen.length === 1 ? '' : 's'}
            </button>
          </div>
        </>
      )}

      {error ? <p className="text-destructive text-xs">{error}</p> : null}
    </div>
  )
}
