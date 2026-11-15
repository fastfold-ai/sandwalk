import { type RefObject, useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'

/** First paint of a long chat. Enough to fill the screen, not the whole history. */
export const CHAT_TAIL = 16
/**
 * Older rows mounted per frame after the tail is on screen. The size
 * adapts to how long the last chunk took, so a fast machine finishes the
 * history in a few frames and a slow one never freezes: measured with
 * `pnpm e2e:bench` (long-chat), fixed chunks of 40+ blocked the page
 * 75–150 ms at a time.
 */
export const CHAT_CHUNK = 20
const CHAT_CHUNK_MIN = 10
const CHAT_CHUNK_MAX = 160
/** A chunk that fits well inside a frame may grow; one over this shrinks. */
const FAST_CHUNK_MS = 10
const SLOW_CHUNK_MS = 32

export function nextChunkSize(size: number, elapsedMs: number): number {
  if (elapsedMs < FAST_CHUNK_MS) return Math.min(CHAT_CHUNK_MAX, size * 2)
  if (elapsedMs > SLOW_CHUNK_MS) {
    return Math.max(CHAT_CHUNK_MIN, Math.floor(size / 2))
  }
  return size
}

/**
 * Chats the user left scrolled up. Their saved position is an offset into
 * the whole history, so they mount whole; a chat left at the bottom (or
 * never opened) mounts from the newest rows backwards.
 */
const scrolledUpChats = new Set<string>()

/** `useChatScroll` reports where each chat was left. */
export function markChatScrolledUp(sessionId: string, scrolledUp: boolean) {
  if (scrolledUp) scrolledUpChats.add(sessionId)
  else scrolledUpChats.delete(sessionId)
}

function initialCount(sessionId: string | null): number {
  return sessionId && scrolledUpChats.has(sessionId)
    ? Number.POSITIVE_INFINITY
    : CHAT_TAIL
}

function chatViewport(root: HTMLElement | null): HTMLElement | null {
  return (
    root?.querySelector<HTMLElement>('[data-radix-scroll-area-viewport]') ??
    null
  )
}

function turnNode(root: HTMLElement | null, messageId: string) {
  return (
    chatViewport(root)?.querySelector<HTMLElement>(
      `[data-chat-turn="${CSS.escape(messageId)}"]`
    ) ?? null
  )
}

/**
 * Mount a long chat from the newest rows backwards. Opening a chat with
 * hundreds of rows used to render all of them before the first paint; now
 * the last screen paints at once and history fills in a chunk per frame,
 * with whatever is on screen held in place while rows are added above.
 */
export function useChatHistoryWindow<T>({
  items,
  enabled,
  sessionId,
  scrollRef
}: {
  items: T[]
  enabled: boolean
  sessionId: string | null
  scrollRef: RefObject<HTMLDivElement | null>
}) {
  const [count, setCount] = useState(() => initialCount(sessionId))
  const sessionRef = useRef(sessionId)
  if (sessionRef.current !== sessionId) {
    sessionRef.current = sessionId
    setCount(initialCount(sessionId))
  }

  const chunkRef = useRef(CHAT_CHUNK)
  const total = items.length
  const partial = enabled && count < total
  useEffect(() => {
    if (!partial) return
    const frame = requestAnimationFrame(() => {
      // Pin a row that is already mounted and put it back where it was.
      // Measuring and committing in one task means a scroll cannot land
      // in between, and it is a no-op where the browser anchors scroll
      // itself (Chromium) while still correct where it does not (WebKit).
      const viewport = chatViewport(scrollRef.current)
      const anchor = viewport?.querySelector<HTMLElement>(
        '[data-chat-rows] > *'
      )
      const before = anchor?.getBoundingClientRect().top
      const started = performance.now()
      const size = chunkRef.current
      flushSync(() => {
        setCount(current => Math.min(total, current + size))
      })
      chunkRef.current = nextChunkSize(size, performance.now() - started)
      if (!viewport || !anchor?.isConnected || before == null) return
      const moved = anchor.getBoundingClientRect().top - before
      if (Math.abs(moved) >= 1) viewport.scrollTop += moved
    })
    return () => cancelAnimationFrame(frame)
  }, [count, partial, scrollRef, total])

  const shown = partial ? items.slice(-count) : items

  const pendingJumpRef = useRef<string | null>(null)
  useEffect(() => {
    const messageId = pendingJumpRef.current
    if (!messageId) return
    const target = turnNode(scrollRef.current, messageId)
    if (!target) return
    pendingJumpRef.current = null
    target.scrollIntoView({ block: 'start', behavior: 'smooth' })
  }, [scrollRef, shown.length])

  const jumpToTurn = (messageId: string) => {
    const target = turnNode(scrollRef.current, messageId)
    if (target) {
      target.scrollIntoView({ block: 'start', behavior: 'smooth' })
      return
    }
    // Not mounted yet: mount everything, then jump once it exists.
    pendingJumpRef.current = messageId
    setCount(total)
  }

  return { shown, jumpToTurn }
}
