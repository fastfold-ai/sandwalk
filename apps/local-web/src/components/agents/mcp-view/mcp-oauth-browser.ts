import { isTauri, openInSystemBrowser } from '@/lib/desktop'

export type McpOAuthWatch = {
  /** Stop focus/interval polling (e.g. after postMessage or unmount). */
  dispose: () => void
}

/** Return `true` when OAuth is complete so polling stops. */
type ReturnHandler = () => boolean | void | Promise<boolean | void>

const POLL_MS = 2000
const FOCUS_DELAY_MS = 400
const WATCH_TIMEOUT_MS = 3 * 60 * 1000

let activeDispose: (() => void) | null = null

/** Stop any in-flight OAuth return watch (safe to call from postMessage handlers). */
export function disposeMcpOAuthWatch(): void {
  activeDispose?.()
  activeDispose = null
}

function startReturnWatch(onReturn: ReturnHandler): () => void {
  let disposed = false
  let inflight = false

  const tick = () => {
    if (disposed || inflight) return
    inflight = true
    void Promise.resolve(onReturn())
      .then(done => {
        if (done === true) dispose()
      })
      .catch(() => {
        /* refresh errors are non-fatal while waiting */
      })
      .finally(() => {
        inflight = false
      })
  }

  const onFocus = () => {
    window.setTimeout(tick, FOCUS_DELAY_MS)
  }
  window.addEventListener('focus', onFocus)
  const intervalId = window.setInterval(tick, POLL_MS)
  const timeoutId = window.setTimeout(() => dispose(), WATCH_TIMEOUT_MS)

  function dispose() {
    if (disposed) return
    disposed = true
    window.removeEventListener('focus', onFocus)
    window.clearInterval(intervalId)
    window.clearTimeout(timeoutId)
    if (activeDispose === dispose) activeDispose = null
  }

  activeDispose = dispose
  // Immediate tick so a late return after tokens land still refreshes quickly.
  tick()
  return dispose
}

/**
 * Open the MCP OAuth authorize URL.
 *
 * Desktop (Tauri) uses the system browser — `window.opener` is null there, so
 * the callback page cannot postMessage. We poll + listen for window focus until
 * `disposeMcpOAuthWatch()` / the returned dispose / timeout.
 *
 * Web uses a named popup (postMessage works when COOP allows opener).
 */
export async function openMcpOAuthBrowser(
  url: string,
  onReturn?: ReturnHandler
): Promise<McpOAuthWatch> {
  disposeMcpOAuthWatch()

  if (isTauri()) {
    await openInSystemBrowser(url)
    const dispose = onReturn ? startReturnWatch(onReturn) : () => {}
    return { dispose }
  }

  const popup = window.open(
    url,
    'fastfold-mcp-oauth',
    'width=560,height=720'
  )
  if (!popup) {
    throw new Error(
      'The browser blocked the OAuth popup. Allow popups for Sandwalk and try again.'
    )
  }

  // Also watch in the web app: some IdPs set COOP and clear `window.opener`.
  const dispose = onReturn ? startReturnWatch(onReturn) : () => {}
  return { dispose }
}
