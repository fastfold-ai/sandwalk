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

export function useChatScroll({
  sessionId,
  messagesLoaded,
  messagesLength,
  conversationTimelineLength
}: UseChatScrollArgs) {
  const chatScrollRef = useRef<HTMLDivElement | null>(null)
  const chatEndRef = useRef<HTMLDivElement | null>(null)
  const [showScrollToBottom, setShowScrollToBottom] = useState(false)
  const chatPinnedSessionRef = useRef<string | null>(null)

  const scrollChatToBottom = useCallback(() => {
    const root = chatScrollRef.current
    const viewport = root?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null
    if (viewport) {
      viewport.scrollTop = viewport.scrollHeight
      setShowScrollToBottom(false)
      return
    }
    chatEndRef.current?.scrollIntoView({ block: 'end' })
    setShowScrollToBottom(false)
  }, [])

  const updateScrollToBottomVisibility = useCallback(() => {
    const root = chatScrollRef.current
    const viewport = root?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null
    if (!viewport) {
      setShowScrollToBottom(false)
      return
    }
    const distanceFromBottom =
      viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight
    setShowScrollToBottom(distanceFromBottom > 96)
  }, [])

  useEffect(() => {
    if (!sessionId || !messagesLoaded || messagesLength === 0) {
      setShowScrollToBottom(false)
      return
    }
    const root = chatScrollRef.current
    const viewport = root?.querySelector(
      '[data-radix-scroll-area-viewport]'
    ) as HTMLElement | null
    if (!viewport) return

    updateScrollToBottomVisibility()
    viewport.addEventListener('scroll', updateScrollToBottomVisibility, {
      passive: true
    })
    const observer = new ResizeObserver(() => updateScrollToBottomVisibility())
    observer.observe(viewport)
    const content = viewport.firstElementChild
    if (content) observer.observe(content)

    return () => {
      viewport.removeEventListener('scroll', updateScrollToBottomVisibility)
      observer.disconnect()
    }
  }, [
    conversationTimelineLength,
    messagesLength,
    messagesLoaded,
    sessionId,
    updateScrollToBottomVisibility
  ])

  // Show the latest message when opening/loading a session with history.
  // Only pin once per session — do not keep forcing scroll while streaming.
  useLayoutEffect(() => {
    if (!sessionId || !messagesLoaded || messagesLength === 0) return
    if (chatPinnedSessionRef.current === sessionId) return
    chatPinnedSessionRef.current = sessionId
    scrollChatToBottom()
    const frame = window.requestAnimationFrame(() => scrollChatToBottom())
    const timers = [80, 250, 600].map(ms =>
      window.setTimeout(() => scrollChatToBottom(), ms)
    )
    return () => {
      window.cancelAnimationFrame(frame)
      for (const timer of timers) window.clearTimeout(timer)
    }
  }, [messagesLength, messagesLoaded, scrollChatToBottom, sessionId])

  return {
    chatScrollRef,
    chatEndRef,
    showScrollToBottom,
    scrollChatToBottom
  }
}
