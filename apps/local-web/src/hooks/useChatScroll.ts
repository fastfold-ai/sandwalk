import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState
} from 'react'

type UseChatScrollArgs = {
  sessionId: string | null
  messagesLoaded: boolean
  messagesLength: number
  conversationTimelineLength: number
}

type SessionScrollMemory = {
  stickToBottom: boolean
  scrollTop: number
}

const NEAR_BOTTOM_PX = 96

function getChatViewport(root: HTMLElement | null) {
  if (!root) return null
  return root.querySelector(
    '[data-radix-scroll-area-viewport]'
  ) as HTMLElement | null
}

function distanceFromBottom(viewport: HTMLElement) {
  return viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight
}

/**
 * Per-session scroll affinity: remember stick-to-bottom vs offset, restore on
 * tab return. Pairs with `key={sessionId}` on ChatTranscript (fresh viewport).
 */
export function useChatScroll({
  sessionId,
  messagesLoaded,
  messagesLength,
  conversationTimelineLength
}: UseChatScrollArgs) {
  const chatScrollRef = useRef<HTMLDivElement | null>(null)
  const chatEndRef = useRef<HTMLDivElement | null>(null)
  const [showScrollToBottom, setShowScrollToBottom] = useState(false)
  const memoryRef = useRef<Record<string, SessionScrollMemory>>({})
  const stickToBottomRef = useRef(true)
  const activeSessionRef = useRef<string | null>(null)
  const appliedForRef = useRef<string | null>(null)

  const rememberActive = useCallback(() => {
    const id = activeSessionRef.current
    const viewport = getChatViewport(chatScrollRef.current)
    if (!id || !viewport) return
    const distance = distanceFromBottom(viewport)
    const stick = distance < NEAR_BOTTOM_PX
    stickToBottomRef.current = stick
    memoryRef.current[id] = {
      stickToBottom: stick,
      scrollTop: viewport.scrollTop
    }
    setShowScrollToBottom(distance > NEAR_BOTTOM_PX)
  }, [])

  const scrollChatToBottom = useCallback(() => {
    const id = activeSessionRef.current
    const viewport = getChatViewport(chatScrollRef.current)
    if (viewport) {
      viewport.scrollTop = viewport.scrollHeight
      viewport.scrollTop = viewport.scrollHeight
    }
    chatEndRef.current?.scrollIntoView({ block: 'end', behavior: 'auto' })
    stickToBottomRef.current = true
    if (id) {
      memoryRef.current[id] = { stickToBottom: true, scrollTop: 0 }
    }
    setShowScrollToBottom(false)
  }, [])

  const applySessionScroll = useCallback(() => {
    const id = activeSessionRef.current
    const viewport = getChatViewport(chatScrollRef.current)
    if (!id || !viewport) return false
    const mem = memoryRef.current[id]
    const stick = mem?.stickToBottom ?? true
    stickToBottomRef.current = stick
    if (stick) {
      viewport.scrollTop = viewport.scrollHeight
      chatEndRef.current?.scrollIntoView({ block: 'end', behavior: 'auto' })
      setShowScrollToBottom(false)
    } else {
      viewport.scrollTop = mem?.scrollTop ?? 0
      setShowScrollToBottom(
        distanceFromBottom(viewport) > NEAR_BOTTOM_PX
      )
    }
    return true
  }, [])

  useLayoutEffect(() => {
    activeSessionRef.current = sessionId
    appliedForRef.current = null
    if (!sessionId) {
      stickToBottomRef.current = true
      setShowScrollToBottom(false)
    }
  }, [sessionId])

  // After remount + messages: restore affinity or pin bottom (first visit).
  useLayoutEffect(() => {
    if (!sessionId || !messagesLoaded) return
    if (appliedForRef.current === sessionId) return

    if (messagesLength === 0) {
      // Don't mark applied — cold hydrate still needs a pin when messages arrive.
      stickToBottomRef.current = true
      setShowScrollToBottom(false)
      return
    }

    const run = () => {
      if (activeSessionRef.current !== sessionId) return
      if (applySessionScroll()) appliedForRef.current = sessionId
    }
    run()
    const frame = window.requestAnimationFrame(run)
    const timer = window.setTimeout(run, 40)
    return () => {
      window.cancelAnimationFrame(frame)
      window.clearTimeout(timer)
    }
  }, [
    sessionId,
    messagesLoaded,
    messagesLength,
    conversationTimelineLength,
    applySessionScroll
  ])

  useEffect(() => {
    if (!sessionId || !messagesLoaded || messagesLength === 0) {
      setShowScrollToBottom(false)
      return
    }
    const viewport = getChatViewport(chatScrollRef.current)
    if (!viewport) return

    rememberActive()
    viewport.addEventListener('scroll', rememberActive, { passive: true })
    const observer = new ResizeObserver(() => {
      if (
        activeSessionRef.current === sessionId &&
        stickToBottomRef.current
      ) {
        scrollChatToBottom()
      } else {
        rememberActive()
      }
    })
    observer.observe(viewport)
    const content = viewport.firstElementChild
    if (content) observer.observe(content)

    return () => {
      rememberActive()
      viewport.removeEventListener('scroll', rememberActive)
      observer.disconnect()
    }
  }, [
    conversationTimelineLength,
    messagesLength,
    messagesLoaded,
    sessionId,
    rememberActive,
    scrollChatToBottom
  ])

  return {
    chatScrollRef,
    chatEndRef,
    showScrollToBottom,
    scrollChatToBottom
  }
}
