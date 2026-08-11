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
  await Promise.race([
    Promise.resolve(args.prefetchSessionMessages(args.id)),
    new Promise<void>(resolve => {
      window.setTimeout(resolve, PREFETCH_BUDGET_MS)
    })
  ])
  args.navigate(`/agents/${args.id}`)
}
