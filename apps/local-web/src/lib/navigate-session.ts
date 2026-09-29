import { isSessionGroupId } from '@sandwalk/agent-ui-core'
import type { NavigateFunction } from 'react-router-dom'

/** Max wait for message cache before navigating — keeps tab switches snappy. */
const PREFETCH_BUDGET_MS = 150

/**
 * Open a session tab and navigate once messages are cached (or budget expires).
 * Prefetch keeps running in the background if we navigate early.
 */
export async function navigateToSession(args: {
  id: string
  openSessionTab: (id: string) => void
  prefetchSessionMessages: (id: string) => void | Promise<void>
  navigate: NavigateFunction
}) {
  args.openSessionTab(args.id)
  // FAS-107 Q1: terminals live under their own route (`/terminals/:id`),
  // not `/agents/:id`. Detect by prefix and short-circuit the prefetch
  // (there are no messages to prefetch for a terminal PTY).
  const isTerminal = args.id.startsWith('term_')
  // Group ids (`grp_*`) are tab wrappers, not sessions — the group's own
  // `SessionChatMount`s handle their prefetch per real chat id when they
  // mount. Skip the outer prefetch so we don't 404 on /sessions/grp_*/messages.
  if (!isSessionGroupId(args.id) && !isTerminal) {
    await Promise.race([
      Promise.resolve(args.prefetchSessionMessages(args.id)),
      new Promise<void>(resolve => {
        window.setTimeout(resolve, PREFETCH_BUDGET_MS)
      })
    ])
  }
  args.navigate(isTerminal ? `/terminals/${args.id}` : `/agents/${args.id}`)
}
