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
/*
 * Umbral chico para detectar "el usuario está PEGADO al bottom".
 * Diferente de `NEAR_BOTTOM_PX` que gobierna sticky-on-content (SSE) y el
 * botón scroll-to-bottom. Este solo lo usa el ResizeObserver para decidir
 * si mantener al usuario al bottom cuando el viewport SE ACHICA sin llegar
 * contenido nuevo (típico en split view: el composer aparece al recuperar
 * focus y sube el padding-bottom del transcript). Si estaba dentro de
 * 24 px del bottom real ANTES del resize, seguimos ahí después.
 */
const PINNED_TO_BOTTOM_PX = 24

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
  /*
   * `pinnedToBottomRef` refleja "distance < PINNED_TO_BOTTOM_PX" al último
   * scroll event conocido. El ResizeObserver lo consulta cuando el viewport
   * se achica sin contenido nuevo (padding grew) para saber si el usuario
   * estaba REALMENTE pegado al bottom antes del resize.
   */
  const pinnedToBottomRef = useRef(true)
  const activeSessionRef = useRef<string | null>(null)
  const appliedForRef = useRef<string | null>(null)

  const rememberActive = useCallback(() => {
    const id = activeSessionRef.current
    const viewport = getChatViewport(chatScrollRef.current)
    if (!id || !viewport) return
    const distance = distanceFromBottom(viewport)
    const stick = distance < NEAR_BOTTOM_PX
    stickToBottomRef.current = stick
    pinnedToBottomRef.current = distance <= PINNED_TO_BOTTOM_PX
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
    /*
     * El observer distingue tres causas de resize:
     *
     *   1. `scrollHeight` creció → llegó contenido nuevo (SSE, mensaje
     *      recién enviado, tool card expandida). Si el usuario estaba
     *      sticky (dentro de `NEAR_BOTTOM_PX`), mantenemos su vista al fondo.
     *   2. `clientHeight` se ACHICÓ sin content growth → cambio de layout
     *      externo que come espacio abajo (típico: composer aparece en
     *      split view al recuperar focus, sube el padding-bottom). Si el
     *      usuario estaba PEGADO al bottom real (dentro de
     *      `PINNED_TO_BOTTOM_PX` = 24 px, medido justo antes del resize
     *      vía `pinnedToBottomRef`), lo mantenemos ahí — así el composer
     *      entrante no le tapa los últimos mensajes. Si no estaba pegado,
     *      respetamos su posición.
     *   3. Cualquier otro caso (viewport creció, o cero cambios) → solo
     *      refrescamos la memoria.
     *
     * Sin este split, cualquier cambio de padding disparaba
     * `scrollChatToBottom` si el usuario estaba dentro de `NEAR_BOTTOM_PX`
     * (96 px), y en split view veíamos un "mini scroll" cada vez que se
     * cambiaba el focus aunque el usuario estuviera leyendo un mensaje
     * reciente pero no pegado al fondo.
     */
    const lastScrollHeightRef = { current: viewport.scrollHeight }
    const lastClientHeightRef = { current: viewport.clientHeight }
    /*
     * Debounce del observer vía `requestAnimationFrame`: durante una
     * transición de padding (~300 ms en split view) el ResizeObserver
     * puede dispararse ~18 veces (una por frame). Con este dedup se
     * procesa como máximo una vez por frame; si el navegador nos
     * saltea frames por carga, se procesa el próximo. Efecto: menos
     * trabajo redundante en cada `layout tick`, misma UX final.
     */
    let rafId: number | null = null
    const observer = new ResizeObserver(() => {
      if (rafId != null) return
      rafId = window.requestAnimationFrame(() => {
        rafId = null
        if (activeSessionRef.current !== sessionId) return
        const currentScrollHeight = viewport.scrollHeight
        const currentClientHeight = viewport.clientHeight
        const contentGrew = currentScrollHeight > lastScrollHeightRef.current
        const viewportShrunk =
          currentClientHeight < lastClientHeightRef.current
        lastScrollHeightRef.current = currentScrollHeight
        lastClientHeightRef.current = currentClientHeight

        if (contentGrew) {
          if (stickToBottomRef.current) scrollChatToBottom()
          else rememberActive()
          return
        }
        if (viewportShrunk && pinnedToBottomRef.current) {
          scrollChatToBottom()
          return
        }
        rememberActive()
      })
    })
    observer.observe(viewport)
    const content = viewport.firstElementChild
    if (content) observer.observe(content)

    return () => {
      rememberActive()
      viewport.removeEventListener('scroll', rememberActive)
      observer.disconnect()
      if (rafId != null) {
        window.cancelAnimationFrame(rafId)
        rafId = null
      }
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
