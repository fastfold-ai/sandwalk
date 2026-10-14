import type { ExternalAgentKind } from '@sandwalk/agent-ui-core'

import { cn } from '@/lib/utils'

/**
 * Monochrome marks for the coding-agent CLIs Sandwalk can launch, detect in
 * a terminal, and import from. `currentColor` so they sit in any chip.
 */
export function ExternalAgentIcon({
  kind,
  className
}: {
  kind: ExternalAgentKind
  className?: string
}) {
  const cls = cn('size-3.5 shrink-0', className)
  if (kind === 'claude') {
    return (
      <svg viewBox="0 0 16 16" aria-hidden className={cls}>
        <path
          fill="currentColor"
          d="M8 1.2 9.1 6 14 4.6 10.2 8 14 11.4 9.1 10 8 14.8 6.9 10 2 11.4 5.8 8 2 4.6 6.9 6Z"
        />
      </svg>
    )
  }
  if (kind === 'codex') {
    return (
      <svg viewBox="0 0 16 16" aria-hidden className={cls}>
        <circle cx="8" cy="8" r="2.1" fill="currentColor" />
        <circle cx="8" cy="2.4" r="1.15" fill="currentColor" />
        <circle cx="12.6" cy="5.2" r="1.15" fill="currentColor" />
        <circle cx="12.6" cy="10.8" r="1.15" fill="currentColor" />
        <circle cx="8" cy="13.6" r="1.15" fill="currentColor" />
        <circle cx="3.4" cy="10.8" r="1.15" fill="currentColor" />
        <circle cx="3.4" cy="5.2" r="1.15" fill="currentColor" />
      </svg>
    )
  }
  if (kind === 'opencode') {
    return (
      <svg viewBox="0 0 16 16" aria-hidden className={cls}>
        <rect
          x="1.75"
          y="2.25"
          width="12.5"
          height="11.5"
          rx="2"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        <path
          d="M5 6.2 7.2 8 5 9.8M8.4 10h2.8"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    )
  }
  // fx: a slanted f over x, the way fx.sh draws its wordmark.
  return (
    <svg viewBox="0 0 16 16" aria-hidden className={cls}>
      <path
        d="M4.2 13 6.6 3h2.2M4.3 7.6h3.4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="m8.6 8.4 3.9 4.6M12.9 8.4 8.6 13"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  )
}

export const EXTERNAL_AGENT_LABELS: Record<ExternalAgentKind, string> = {
  claude: 'Claude Code',
  codex: 'Codex',
  opencode: 'OpenCode',
  fx: 'fx'
}

export const EXTERNAL_AGENT_KINDS: ExternalAgentKind[] = [
  'claude',
  'codex',
  'opencode',
  'fx'
]

/** Agents whose own session file Sandwalk can write for a native `resume`. */
export const NATIVE_HANDOFF_KINDS: ReadonlySet<ExternalAgentKind> = new Set([
  'claude',
  'codex'
])

export function isExternalAgentKind(value: unknown): value is ExternalAgentKind {
  return (
    value === 'claude' ||
    value === 'codex' ||
    value === 'opencode' ||
    value === 'fx'
  )
}
