/**
 * Reconnect decisions for a terminal's PTY socket, kept free of DOM/xterm
 * so they can be unit-tested.
 *
 * The server owns the shell processes. When it restarts (dev loop, menubar
 * relaunch, update) every PTY dies with it. The client must therefore keep
 * trying forever (never a dead "max attempts" state) and, once the server
 * is back, spawn a replacement shell when the old PTY id is gone.
 */

/** Cap del backoff en ms. Después de este techo se mantiene constante. */
export const RECONNECT_CAP_MS = 10_000
/** Base del backoff en ms. Primer retry ~500ms. */
export const RECONNECT_BASE_MS = 500
/** After this many misses the terminal prints that it is waiting. */
export const RECONNECT_NOTICE_AFTER = 4

/** Websocket close code the server sends when the PTY id is unknown. */
export const PTY_GONE_CLOSE_CODE = 4404

/** Delay before the next attempt; exponential, jittered, capped, never gives up. */
export function reconnectDelayMs(attempt: number, jitter: number = Math.random()): number {
  const base = RECONNECT_BASE_MS * 2 ** Math.max(0, attempt)
  return Math.min(base + Math.floor(jitter * 200), RECONNECT_CAP_MS)
}

/** Show the "waiting for the server" line exactly once per outage. */
export function shouldShowWaitingNotice(attempt: number, alreadyShown: boolean): boolean {
  return attempt >= RECONNECT_NOTICE_AFTER && !alreadyShown
}

/** A 4404 means the server is up but this PTY is gone: forget the handle. */
export function shouldDropPtyHandle(closeCode: number | undefined): boolean {
  return closeCode === PTY_GONE_CLOSE_CODE
}

/**
 * Whether a reconnect attempt must re-check the PTY id against the server
 * before dialing. A server restart kills every PTY, but a handshake that
 * fails before `accept()` reaches the browser as 1006, not 4404, so the
 * close code alone cannot tell "server down" from "PTY gone". Any attempt
 * after the first therefore verifies the id; `livePtyIds` is what the
 * server currently lists for this terminal.
 */
export function ptyHandleIsStale(
  attempt: number,
  ptyId: string | null,
  livePtyIds: readonly string[]
): boolean {
  if (attempt === 0 || ptyId === null) return false
  return !livePtyIds.includes(ptyId)
}

/**
 * When listing PTYs returns nothing for a terminal that was already
 * hydrated, the shell died with the server. The caller creates a new PTY
 * and tells the user; a first-ever connect (not hydrated) is just a new
 * terminal and prints nothing.
 */
export function isRespawn(existingCount: number, hydrated: boolean): boolean {
  return existingCount === 0 && hydrated
}
