import '@xterm/xterm/css/xterm.css'

import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { listen } from '@tauri-apps/api/event'
import { FitAddon } from '@xterm/addon-fit'
import { WebglAddon } from '@xterm/addon-webgl'
import { Terminal as XTerm } from '@xterm/xterm'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import {
  notifyTerminalCommandFinished,
  notifyTerminalCustom
} from '@/lib/browser-notifications'
import { getFocusedItemId } from '@/lib/focused-item'
import { getTerminalLongRunningThresholdMs } from '@/lib/notification-settings'
import { perfCount, perfTrackTerminal } from '@/lib/perf-probe'
import { markTerminalActivity } from '@/lib/terminal-attention'
import { takeTerminalStartup } from '@/lib/terminal-startup'
import {
  buildTerminalTheme,
  isDocumentDark,
  watchTerminalTheme
} from '@/lib/terminal-theme'
import { isExternalAgentKind } from '@/components/agents/ExternalAgentIcon'
import { useTerminalsStore } from '@/lib/terminals-store'

import {
  isRespawn,
  ptyHandleIsStale,
  reconnectDelayMs,
  shouldDropPtyHandle,
  shouldShowWaitingNotice
} from './reconnect-policy'
import { useTerminalLayer } from './terminal-layer-registry'

/**
 * FAS-107 X4.2 · Terminal portal host reescrito con ciclo de vida
 * separado — patrón VSCode `_attached`.
 *
 * Cambios arquitectónicos vs X3:
 *
 * Antes: un solo `useEffect` con dep `[hostNode]` creaba el xterm y
 * también hacía cleanup con `term.dispose()`. Cada vez que el hostNode
 * cambiaba (por re-render del portal, cambio de layerRoot), el cleanup
 * destruía el xterm y el buffer se perdía.
 *
 * Ahora dos efectos con responsabilidades separadas:
 *
 * 1. `useEffect(..., [])` (deps vacías) — se ejecuta UNA sola vez al
 *    mount del componente. Crea el xterm, la conexión WS, los
 *    listeners globales (resize, scroll, visibility, theme). Cleanup
 *    solo en unmount real (cuando el terminal se elimina del store
 *    Zustand — decisión explícita del user, no cambio de tab).
 *
 * 2. `useEffect(..., [hostNode])` — attach del xterm al div del portal.
 *    Primera vez: `term.open(hostNode)`. Siguientes: `hostNode.appendChild(term.element)`.
 *    Sin dispose en cleanup — el xterm sobrevive al cambio de host.
 *
 * Este es el patrón oficial de xterm.js (issues #4978, #1323): `open()`
 * una sola vez, el buffer vive en `term.element`, moverlo lo preserva.
 *
 * Cubre además:
 * - Reconexión WS con backoff exponencial (Fix 3 de Capa 1).
 * - `document.visibilitychange` verifica el WS al volver de background
 *   (Fix 4 de Capa 1).
 * - Guard duro del `fit.proposeDimensions` cuando devuelve dimensiones
 *   inválidas (Fix 5 de Capa 1).
 * - Propagación del `contextmenu` al placeholder via registry
 *   (X3 Fase 5 reintroducida como responsabilidad interna).
 */

type PtyInfo = {
  id: string
  session_id: string
  title: string
}

/**
 * FAS-107 X4 Capa 2 · intervalo de guardado throttled del snapshot.
 * Cada 30s se serializa el buffer visible y se manda al backend. Así
 * un crash de Sandwalk pierde ~30s de output máximo. Al Cmd+Q se
 * fuerza un último guardado (Rust emite el evento).
 */
const SNAPSHOT_SAVE_INTERVAL_MS = 30_000
/** Evento que Rust emite al `RunEvent::ExitRequested` para forzar save. */
const SNAPSHOT_FORCE_SAVE_EVENT = 'sandwalk:force-save-snapshots'
/**
 * Debounce for `fit.proposeDimensions()` + `term.resize()` + the PTY
 * resize RPC. CSS reflows (active-pane change in a split, window
 * resize) move the placeholder several times within a few ms; fitting
 * on every frame forces layout reads per terminal and floods the shell
 * with SIGWINCH, which is what clips scrollback (FAS-121). Following the
 * placeholder visually stays immediate — only the fit waits.
 */
const RESIZE_DEBOUNCE_MS = 50
/** Max bytes of keyboard input held while the PTY socket is connecting. */
const PENDING_INPUT_LIMIT = 4096

export function TerminalPortalHost({
  client,
  terminalId
}: {
  client: LocalAgentClient
  terminalId: string
}) {
  const registry = useTerminalLayer()
  const layerRoot = registry.getLayerRoot()

  const [hostNode, setHostNode] = useState<HTMLDivElement | null>(null)
  const hostRef = useRef<HTMLDivElement | null>(null)
  hostRef.current = hostNode
  const termRef = useRef<XTerm | null>(null)
  const fitRef = useRef<FitAddon | null>(null)
  const webglRef = useRef<WebglAddon | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const ptyRef = useRef<PtyInfo | null>(null)
  const attachedRef = useRef(false)
  /**
   * FAS-107 X4 Capa 2 · marca si ya hidratamos el buffer con el
   * snapshot persistido. Solo aplica al PRIMER connect del ciclo de
   * vida del componente. Las reconexiones (WS timeout, etc.) NO deben
   * re-hidratar — el buffer ya está en memoria.
   */
  const hydratedRef = useRef(false)
  const lastDimsRef = useRef<{ cols: number; rows: number }>({
    cols: -1,
    rows: -1
  })
  // FAS-107 · Fase 1c · ref al handler de eventos PTY del WS. Vive como
  // ref porque el `ws.onmessage` se registra una sola vez y no debe
  // re-crearse cada render. El body del handler se asigna abajo y
  // consulta el store de terminales en el momento (título puede cambiar
  // por rename) y el settings del umbral (puede cambiar en runtime).
  const handlePtyEventRef = useRef<((event: unknown) => void) | null>(null)
  handlePtyEventRef.current = (raw: unknown) => {
    if (!raw || typeof raw !== 'object') return
    const event = raw as {
      kind?: string
      exitCode?: number | null
      durationMs?: number | null
      title?: string
      body?: string
      agent?: string | null
    }
    const terminal = useTerminalsStore
      .getState()
      .terminals.find(t => t.id === terminalId)
    const terminalTitle = terminal?.title ?? null
    const viewing = getFocusedItemId() === terminalId
    if (event.kind === 'agent.changed') {
      // Backend probed the PTY foreground process: a coding-agent CLI
      // started or exited. Drives the tab / sidebar icon swap.
      useTerminalsStore.getState().patch(terminalId, {
        agent: isExternalAgentKind(event.agent) ? event.agent : null
      })
      return
    }
    if (event.kind === 'command.finished') {
      // Los comandos cortos NO gritan por notificación nativa — pero sí
      // marcan attention si el usuario no estaba mirando ese pane, para
      // que el chip azul en el sidebar cuente la actividad.
      if (!viewing) markTerminalActivity(terminalId)
      const threshold = getTerminalLongRunningThresholdMs()
      const durationMs = event.durationMs ?? 0
      const failed = event.exitCode !== 0 && event.exitCode !== null
      // Los fallos siempre notifican (aunque sean cortos). Éxitos solo
      // si superan el umbral configurado.
      if (!failed && durationMs < threshold) return
      notifyTerminalCommandFinished({
        terminalId,
        terminalTitle,
        exitCode: event.exitCode ?? null,
        durationMs: event.durationMs ?? null,
        viewingTerminal: viewing
      })
      return
    }
    if (event.kind === 'notify') {
      // OSC 9 / OSC 777 son intención explícita — pasan sin gate.
      if (!viewing) markTerminalActivity(terminalId)
      notifyTerminalCustom({
        terminalId,
        terminalTitle,
        title: event.title ?? null,
        body: event.body ?? null
      })
    }
    // 'command.started' es solo timing en el backend, no requiere acción.
  }
  const [, setLayerVersion] = useState(0)

  // Suscripción al registry: cuando el placeholder cambia
  // (registrado/desregistrado), forzamos re-render para que el portal
  // se re-renderee con el layerRoot fresco y disparamos re-posicionamiento.
  useEffect(() => {
    const listener = () => {
      setLayerVersion(v => v + 1)
      schedulePosition()
    }
    const unsub = registry.subscribe(terminalId, listener)
    return unsub
    // schedulePosition se resuelve en tiempo de invocación.
  }, [registry, terminalId])

  const rafRef = useRef<number | null>(null)
  const schedulePosition = () => {
    if (rafRef.current != null) return
    rafRef.current = window.requestAnimationFrame(() => {
      rafRef.current = null
      applyPosition()
    })
  }

  /** Last placeholder box we fitted the xterm to (CSS px). */
  const lastBoxRef = useRef<{ width: number; height: number }>({
    width: -1,
    height: -1
  })
  const fitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  /**
   * Fit the xterm grid to the host. `term.resize` fires `term.onResize`,
   * which owns the (deduped) PTY resize RPC.
   */
  const applyFit = () => {
    fitTimerRef.current = null
    const fit = fitRef.current
    const term = termRef.current
    if (!fit || !term || !hostRef.current) return
    perfCount('terminal.fit')
    try {
      const dims = fit.proposeDimensions()
      // Guard duro: fit puede devolver dimensiones degeneradas durante
      // transiciones de layout. Si es el caso, no propagamos al PTY.
      if (!dims || dims.cols < 10 || dims.rows < 3) return
      if (dims.cols === term.cols && dims.rows === term.rows) return
      term.resize(dims.cols, dims.rows)
    } catch {
      // ignore — cualquier miscálculo del fit se corrige en el siguiente frame
    }
  }

  const scheduleFit = (immediate: boolean) => {
    if (fitTimerRef.current != null) {
      clearTimeout(fitTimerRef.current)
      fitTimerRef.current = null
    }
    if (immediate) {
      applyFit()
      return
    }
    fitTimerRef.current = setTimeout(applyFit, RESIZE_DEBOUNCE_MS)
  }

  /**
   * Follow the placeholder. Positioning is one `getBoundingClientRect`
   * plus style writes and runs on every scheduled frame; the expensive
   * `fit` only runs when the box actually changed size (debounced).
   */
  /**
   * GPU renderer only while the terminal is on screen. WebKit allows ~16
   * WebGL contexts per page and evicts the oldest; with a dozen terminals
   * mounted that meant constant "context lost → dispose → DOM fallback"
   * churn. Hidden terminals keep their buffer in the DOM renderer at zero
   * GPU cost and get WebGL back the moment they are shown.
   */
  const setGpuRenderer = (on: boolean) => {
    const term = termRef.current
    if (!term || !attachedRef.current) return
    if (on) {
      if (webglRef.current) return
      try {
        const webgl = new WebglAddon()
        webgl.onContextLoss(() => {
          webgl.dispose()
          if (webglRef.current === webgl) webglRef.current = null
          perfCount('terminal.webglLost')
        })
        term.loadAddon(webgl)
        webglRef.current = webgl
        perfCount('terminal.webglOn')
      } catch {
        webglRef.current = null
        perfCount('terminal.webglUnavailable')
      }
      return
    }
    if (!webglRef.current) return
    try {
      webglRef.current.dispose()
    } catch {
      // ignore
    }
    webglRef.current = null
    perfCount('terminal.webglOff')
  }

  const applyPosition = () => {
    const host = hostRef.current
    if (!host) return
    perfCount('terminal.applyPosition')
    const entry = registry.getPlaceholder(terminalId)
    if (!entry || !entry.node.isConnected) {
      host.style.display = 'none'
      setGpuRenderer(false)
      return
    }
    const rect = entry.node.getBoundingClientRect()
    if (rect.width < 1 || rect.height < 1) {
      host.style.display = 'none'
      setGpuRenderer(false)
      return
    }
    host.style.display = ''
    setGpuRenderer(true)
    host.style.position = 'fixed'
    host.style.top = `${rect.top}px`
    host.style.left = `${rect.left}px`
    host.style.width = `${rect.width}px`
    host.style.height = `${rect.height}px`
    host.style.pointerEvents = 'auto'
    const last = lastBoxRef.current
    const sizeChanged =
      Math.abs(rect.width - last.width) >= 0.5 ||
      Math.abs(rect.height - last.height) >= 0.5
    if (!sizeChanged) return
    const firstFit = last.width < 0
    lastBoxRef.current = { width: rect.width, height: rect.height }
    // First layout after attach fits right away so the prompt renders at
    // the correct width; later size changes are debounced.
    scheduleFit(firstFit)
  }

  // Effect 1 · Crear xterm + WS + listeners globales. Corre UNA vez al
  // mount del componente. El componente solo se desmonta cuando el
  // terminal deja de existir en el store Zustand (por acción explícita
  // del usuario). Cambios de tab/split/vista NO desmontan este efecto.
  useEffect(() => {
    if (termRef.current) return

    const term = new XTerm({
      cursorBlink: true,
      cursorStyle: 'bar',
      fontSize: 11,
      lineHeight: 1.35,
      letterSpacing: 0,
      fontFamily:
        '"SF Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
      theme: buildTerminalTheme(isDocumentDark()),
      convertEol: false,
      allowTransparency: false,
      scrollback: 5000,
      smoothScrollDuration: 0
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    termRef.current = term
    fitRef.current = fit
    perfTrackTerminal(terminalId, term)

    const stopThemeWatch = watchTerminalTheme(() => {
      term.options.theme = buildTerminalTheme(isDocumentDark())
    })

    // Keystrokes typed before the PTY WebSocket is open (the restored
    // snapshot paints a prompt immediately, the socket lands a beat later)
    // are queued and flushed in `ws.onopen` instead of being dropped.
    const pendingInput: string[] = []
    let pendingInputBytes = 0
    term.onData(data => {
      const ws = socketRef.current
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(data)
        return
      }
      if (pendingInputBytes + data.length > PENDING_INPUT_LIMIT) return
      pendingInput.push(data)
      pendingInputBytes += data.length
      perfCount('terminal.inputQueued')
    })

    term.onResize(({ cols, rows }) => {
      if (cols < 10 || rows < 3) return
      if (
        cols === lastDimsRef.current.cols &&
        rows === lastDimsRef.current.rows
      ) {
        return
      }
      lastDimsRef.current = { cols, rows }
      if (
        socketRef.current?.readyState === WebSocket.OPEN &&
        ptyRef.current
      ) {
        perfCount('terminal.ptyResizeRpc')
        void client.updatePtySession(terminalId, ptyRef.current.id, {
          cols,
          rows
        })
      }
    })

    // ---- Conexión WS con reconexión automática ----
    let cancelled = false
    /** Set when PTY bytes arrive; cleared by the periodic snapshot flush. */
    let dirtySinceFlush = false
    let reconnectAttempts = 0
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    /** Printed once per outage so a long reconnect loop stays quiet. */
    let noticeShown = false

    const connectWebSocket = async () => {
      if (cancelled) return
      try {
        // On a reconnect, re-validate the PTY id against the server. A
        // server restart kills every PTY, but the browser reports the dead
        // handshake as code 1006 (not our 4404), so without this the
        // client retried the same dead id forever and the tab stayed on
        // "waiting for the Sandwalk server…" even after it was back.
        if (ptyRef.current && reconnectAttempts > 0) {
          const live = await client.listPtySessions(terminalId)
          if (cancelled) return
          if (
            ptyHandleIsStale(
              reconnectAttempts,
              ptyRef.current.id,
              live.map(info => info.id)
            )
          ) {
            ptyRef.current = null
          }
        }
        if (!ptyRef.current) {
          const existing = await client.listPtySessions(terminalId)
          if (cancelled) return
          // No live PTY: the server restarted and the shell died with it.
          // Spawn a new one so the tab comes back instead of staying dead.
          const respawned = isRespawn(existing.length, hydratedRef.current)
          const info = existing[0] ?? (await client.createPtySession(terminalId))
          if (cancelled) return
          ptyRef.current = {
            id: info.id,
            session_id: info.sessionId,
            title: info.title
          }
          if (respawned) {
            useTerminalsStore.getState().patch(terminalId, { agent: null })
            // Delay the notice: the new shell's startup clears the screen,
            // so anything written before that is wiped.
            window.setTimeout(() => {
              if (cancelled || ptyRef.current?.id !== info.id) return
              term.writeln(
                '\x1b[90m[shell restarted — the server came back; the previous process ended]\x1b[0m'
              )
            }, 900)
          }
          // Seed the agent mark from the list response (e.g. a Capy /
          // handoff launch where the CLI was already running before the
          // xterm mounted). Live changes arrive as `agent.changed` events.
          if (isExternalAgentKind(info.agent)) {
            useTerminalsStore.getState().patch(terminalId, { agent: info.agent })
          }
        }
        const info = ptyRef.current
        // FAS-107 X4 Capa 2 · restaurar buffer persistido ANTES de
        // conectar el WS. Solo la primera vez (`hydratedRef`), no en
        // reconexiones — el buffer ya vive en el xterm en memoria.
        //
        // Approach VSCode/Wave (raw byte replay + dims correctas):
        // 1. Resize xterm a las dims ACTUALES del cliente (fit).
        // 2. Escribir los bytes crudos del PTY viejo.
        // 3. Xterm procesa cada byte con las dims actuales y aplica su
        //    reflow interno — el layout se ve correcto al 100% aunque
        //    la ventana haya cambiado de tamaño entre cerrar y reabrir.
        if (!hydratedRef.current) {
          hydratedRef.current = true
          try {
            // Fit primero para que el resize del xterm ocurra con las
            // dims reales del contenedor. Si el fit falla, seguimos con
            // las dims default (mejor eso que nada).
            try {
              const dims = fit.proposeDimensions()
              if (dims && dims.cols >= 10 && dims.rows >= 3) {
                term.resize(dims.cols, dims.rows)
              }
            } catch {
              // ignore fit failure
            }
            const bytes = await client.getSessionSnapshot(terminalId)
            if (!cancelled && bytes && bytes.length > 0) {
              term.write(bytes)
            }
          } catch {
            // Fallo silencioso: el snapshot es "nice to have", no crítico.
          }
        }
        const ws = new WebSocket(client.ptyConnectUrl(terminalId, info.id))
        ws.binaryType = 'arraybuffer'
        socketRef.current = ws

        ws.onopen = () => {
          if (cancelled) return
          reconnectAttempts = 0
          noticeShown = false
          // A plain socket drop (same PTY still alive) needs no banner; the
          // shell is exactly where it was. Respawn prints its own notice.
          perfCount('terminal.wsOpen')
          if (pendingInput.length > 0) {
            for (const chunk of pendingInput) ws.send(chunk)
            pendingInput.length = 0
            pendingInputBytes = 0
          }
          const startup = takeTerminalStartup(terminalId)
          if (startup) {
            window.setTimeout(() => {
              if (cancelled || socketRef.current !== ws) return
              ws.send(`${startup}\r`)
            }, 400)
          }
          try {
            const dims = fit.proposeDimensions()
            if (dims && dims.cols >= 10 && dims.rows >= 3) {
              term.resize(dims.cols, dims.rows)
              lastDimsRef.current = { cols: dims.cols, rows: dims.rows }
              void client.updatePtySession(terminalId, info.id, {
                cols: dims.cols,
                rows: dims.rows
              })
            }
          } catch {
            // ignore fit failure
          }
        }

        ws.onmessage = event => {
          if (typeof event.data === 'string') {
            // FAS-107 · Fase 1c · frames de texto vienen exclusivamente
            // del dispatcher del backend (io_mixin.py `_dispatch_pty_events`)
            // y transportan eventos estructurados — NO son output para
            // xterm. Si el parse falla, tolerar en silencio (no debe
            // crashear el WS del terminal).
            try {
              const frame = JSON.parse(event.data) as {
                type?: string
                event?: unknown
              }
              if (frame.type === 'pty.event' && frame.event) {
                handlePtyEventRef.current?.(frame.event)
              }
            } catch {
              // ignore malformed text frames
            }
            return
          }
          term.write(new Uint8Array(event.data as ArrayBuffer))
          dirtySinceFlush = true
          // FAS-107 · Fix pre-fase1: antes se comparaba con
          // `window.location.pathname` — falla cuando el terminal
          // vive dentro de un group split (la URL apunta al group,
          // no al terminal). Ahora consulta `getFocusedItemId()` que
          // App.tsx sincroniza con `effectiveSessionId` (activeChatId
          // del split, o route.sessionId si no hay split).
          if (getFocusedItemId() !== terminalId) {
            markTerminalActivity(terminalId)
          }
        }

        ws.onclose = event => {
          if (cancelled) return
          // 4404: the server is up but this PTY is gone. Drop the handle so
          // the next attempt spawns a replacement instead of retrying a
          // dead id.
          if (shouldDropPtyHandle(event.code)) ptyRef.current = null
          if (shouldShowWaitingNotice(reconnectAttempts, noticeShown)) {
            noticeShown = true
            term.writeln(
              '\r\n\x1b[90m[disconnected — waiting for the Sandwalk server…]\x1b[0m'
            )
          }
          const delay = reconnectDelayMs(reconnectAttempts)
          reconnectAttempts += 1
          reconnectTimer = setTimeout(() => {
            reconnectTimer = null
            void connectWebSocket()
          }, delay)
        }

        ws.onerror = () => {
          // El WS cerrará solo y disparará onclose → reconexión con backoff.
        }
      } catch (err) {
        // The REST calls before the socket (list / create PTY) fail while
        // the server is down. Treat like a dropped socket and retry.
        if (cancelled) return
        if (shouldShowWaitingNotice(reconnectAttempts, noticeShown)) {
          noticeShown = true
          term.writeln(
            '\r\n\x1b[90m[disconnected — waiting for the Sandwalk server…]\x1b[0m'
          )
        } else if (reconnectAttempts === 0) {
          console.error('TerminalPortalHost connect failed', err)
        }
        const delay = reconnectDelayMs(reconnectAttempts)
        reconnectAttempts += 1
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null
          void connectWebSocket()
        }, delay)
      }
    }

    void connectWebSocket()

    // ---- Listeners de posicionamiento ----
    const onWindow = () => schedulePosition()
    window.addEventListener('resize', onWindow)
    // Scroll is captured at the window so nested scrollers are seen, but
    // only scrollers that contain this terminal's placeholder can move
    // it. A chat transcript scrolling in another pane must not cost a
    // layout read per terminal per frame.
    const onScroll = (event: Event) => {
      const target = event.target
      if (target === document || target === window) {
        schedulePosition()
        return
      }
      const entry = registry.getPlaceholder(terminalId)
      if (!entry || !(target instanceof Node)) return
      if (target.contains(entry.node)) {
        schedulePosition()
      } else {
        perfCount('terminal.scrollIgnored')
      }
    }
    window.addEventListener('scroll', onScroll, { capture: true })

    const observer = new ResizeObserver(() => schedulePosition())
    let observedNode: HTMLDivElement | null = null
    const syncObserverTarget = () => {
      const entry = registry.getPlaceholder(terminalId)
      const nextNode = entry?.node ?? null
      if (nextNode === observedNode) return
      if (observedNode) observer.unobserve(observedNode)
      if (nextNode) observer.observe(nextNode)
      observedNode = nextNode
    }
    syncObserverTarget()
    const unsubObserver = registry.subscribe(terminalId, () => {
      syncObserverTarget()
      schedulePosition()
    })

    // ---- Visibility change: verificar WS al volver del background ----
    const onVisibilityChange = () => {
      if (document.visibilityState !== 'visible') return
      const ws = socketRef.current
      // Si el WS está cerrado o cerrando, disparar reconexión inmediata
      // (sin esperar al backoff pendiente).
      if (
        !ws ||
        ws.readyState === WebSocket.CLOSED ||
        ws.readyState === WebSocket.CLOSING
      ) {
        if (reconnectTimer) {
          clearTimeout(reconnectTimer)
          reconnectTimer = null
        }
        reconnectAttempts = 0
        void connectWebSocket()
      }
      schedulePosition()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    // ---- FAS-107 X4 Capa 2 · Snapshot throttled + force-flush on quit ----
    // El backend absorbe cada byte del PTY en su propio `output_log`
    // (ver `PtySession.output_log`), así que el frontend NO tiene que
    // serializar. Solo necesita pedirle al backend que flush ese log
    // a disco periódicamente (por si Sandwalk crashea) y al Cmd+Q
    // (para que el disco tenga el estado final antes de que el
    // proceso Python muera).
    const flushSnapshot = async (force = false): Promise<void> => {
      if (cancelled) return
      // Idle terminals have nothing new to persist; with many tabs open the
      // unconditional 30 s flush was a steady drip of POSTs for no change.
      if (!force && !dirtySinceFlush) return
      dirtySinceFlush = false
      try {
        await client.flushSessionSnapshot(terminalId)
      } catch {
        // fallo silencioso — el snapshot es best-effort
      }
    }
    const snapshotInterval = setInterval(() => {
      void flushSnapshot()
    }, SNAPSHOT_SAVE_INTERVAL_MS)
    // Cuando Rust emite `sandwalk:force-save-snapshots` (al Cmd+Q),
    // pedimos flush inmediato al backend.
    let unlistenForceSave: (() => void) | null = null
    void listen(SNAPSHOT_FORCE_SAVE_EVENT, () => {
      void flushSnapshot(true)
    }).then(unlisten => {
      if (cancelled) unlisten()
      else unlistenForceSave = unlisten
    })

    // Cleanup en unmount real (el terminal se eliminó del store).
    return () => {
      cancelled = true
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      unsubObserver()
      observer.disconnect()
      window.removeEventListener('resize', onWindow)
      window.removeEventListener('scroll', onScroll, { capture: true })
      document.removeEventListener('visibilitychange', onVisibilityChange)
      clearInterval(snapshotInterval)
      unlistenForceSave?.()
      stopThemeWatch()
      if (rafRef.current != null) {
        window.cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      if (fitTimerRef.current != null) {
        clearTimeout(fitTimerRef.current)
        fitTimerRef.current = null
      }
      lastBoxRef.current = { width: -1, height: -1 }
      try {
        socketRef.current?.close()
      } catch {
        // ignore
      }
      try {
        webglRef.current?.dispose()
      } catch {
        // ignore
      }
      webglRef.current = null
      try {
        term.dispose()
      } catch {
        // ignore
      }
      perfTrackTerminal(terminalId, null)
      termRef.current = null
      fitRef.current = null
      socketRef.current = null
      ptyRef.current = null
      attachedRef.current = false
      hydratedRef.current = false
    }
    // Deps vacías: el efecto corre una sola vez al mount del componente.
    // client, terminalId, registry son estables por instancia. El
    // hostNode NO debe estar aquí — su cambio no debe destruir el xterm.
  }, [])

  // Effect 2 · Attach del xterm al hostNode. Patrón VSCode `_attached`:
  // primera vez `term.open()`, siguientes `appendChild`. Nunca dispose.
  useEffect(() => {
    const host = hostNode
    const term = termRef.current
    if (!host || !term) return

    if (!attachedRef.current) {
      term.open(host)
      attachedRef.current = true
      // The GPU renderer is attached by `applyPosition` once the terminal is
      // actually visible (see `setGpuRenderer`), not for every mounted tab.
    } else if (term.element && term.element.parentElement !== host) {
      // Reparent: el buffer vive en term.element; moverlo lo preserva.
      host.appendChild(term.element)
    }

    // Reposicionamiento inicial post-attach.
    schedulePosition()

    // ---- Foco + contextmenu del layer ----
    const onMouseDown = () => {
      const entry = registry.getPlaceholder(terminalId)
      entry?.onFocus()
    }
    const onContextMenu = (event: MouseEvent) => {
      const entry = registry.getPlaceholder(terminalId)
      if (entry?.onContextMenu) {
        event.preventDefault()
        event.stopPropagation()
        entry.onContextMenu(event)
      }
    }
    host.addEventListener('mousedown', onMouseDown)
    host.addEventListener('contextmenu', onContextMenu)

    return () => {
      host.removeEventListener('mousedown', onMouseDown)
      host.removeEventListener('contextmenu', onContextMenu)
      // NO dispose del xterm. El buffer sobrevive al cambio de host.
    }
  }, [hostNode])

  if (!layerRoot) return null

  return createPortal(
    <div
      ref={setHostNode}
      data-terminal-portal-host={terminalId}
      style={{ display: 'none' }}
    />,
    layerRoot
  )
}
