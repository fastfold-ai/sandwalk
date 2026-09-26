import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { PtySessionInfo } from '@sandwalk/agent-ui-core'
import { FitAddon } from '@xterm/addon-fit'
import { Terminal as XTerm } from '@xterm/xterm'
import { type RefObject,useCallback, useEffect, useRef } from 'react'

import { copyText } from '@/lib/clipboard'
import { markTerminalActivity } from '@/lib/terminal-attention'
import {
  buildTerminalTheme,
  isDocumentDark,
  watchTerminalTheme
} from '@/lib/terminal-theme'

export type LiveTerminal = {
  info: PtySessionInfo
  term: XTerm
  fit: FitAddon
  socket: WebSocket | null
  container: HTMLDivElement | null
  disposed: boolean
  opened: boolean
  /** T4: last (cols, rows) sent to the PTY. Deduplicates bursts of
   *  updatePtySession that would otherwise flood the shell with
   *  SIGWINCH, which fish/zsh re-render their prompt on and produce
   *  the "character per line" visual bug. */
  lastSentCols: number
  lastSentRows: number
  /** FAS-107 · Fase 1j · pending debounce del `updatePtySession`.
   *  Reflows de CSS (cambio de pane en split, resize de ventana)
   *  disparan onResize N veces en pocos ms. Sin debounce, cada uno
   *  produce un RPC + SIGWINCH; el shell re-renderea su prompt y a
   *  veces pierde líneas del scrollback (relacionado bug #133). */
  pendingResize: ReturnType<typeof setTimeout> | null
}

/**
 * V1: xterm instances viven a nivel de módulo, no dentro del componente
 * React. Sobreviven al unmount del `TerminalPanel` — cambiar de tab,
 * de split, o de layout NO destruye el buffer del terminal. Patrón
 * canónico usado por VSCode, GitHub Codespaces y Warp.
 *
 * Se limpian SOLO cuando el usuario cierra el terminal explícitamente
 * (via `closeTab`/`disposeLive`), no cuando React desmonta el árbol.
 */
const GLOBAL_LIVES: Record<string, LiveTerminal> = {}
const GLOBAL_HOSTS: Record<string, HTMLDivElement | null> = {}

export function useTerminalLive({
  client,
  sessionId,
  renameIdRef
}: {
  client: LocalAgentClient
  sessionId: string
  renameIdRef: RefObject<string | null>
}) {
  // V1: hostsRef y livesRef apuntan a los mismos objetos module-level
  // en todos los re-mounts, así los xterm instances persisten. Los divs
  // host se re-crean con cada mount, pero la referencia se sobrescribe
  // desde los `ref` callbacks — el xterm se re-parenta al nuevo host
  // en `mountActive` cuando detecta que `live.container !== host`.
  const hostsRef = useRef(GLOBAL_HOSTS)
  const livesRef = useRef(GLOBAL_LIVES)
  const darkRef = useRef(isDocumentDark())

  useEffect(() => {
    const apply = () => {
      const nextDark = isDocumentDark()
      darkRef.current = nextDark
      const next = buildTerminalTheme(nextDark)
      for (const live of Object.values(livesRef.current)) {
        if (live.disposed) continue
        live.term.options.theme = next
      }
    }
    apply()
    return watchTerminalTheme(apply)
  }, [])

  // V1: `disposeLive` sólo se llama cuando el usuario cierra un
  // terminal explícitamente (closeTab / deleteTerminal). El unmount
  // del componente NO dispara este cleanup — el xterm sobrevive en
  // el map global hasta que el user decide cerrarlo.
  const disposeLive = useCallback((ptyId: string) => {
    const live = livesRef.current[ptyId]
    if (!live || live.disposed) return
    live.disposed = true
    if (live.pendingResize !== null) {
      clearTimeout(live.pendingResize)
      live.pendingResize = null
    }
    try {
      live.socket?.close()
    } catch {
      // ignore
    }
    try {
      live.term.dispose()
    } catch {
      // ignore
    }
    delete livesRef.current[ptyId]
    delete hostsRef.current[ptyId]
  }, [])

  const connectLive = useCallback(
    (info: PtySessionInfo) => {
      if (livesRef.current[info.id] && !livesRef.current[info.id].disposed) {
        return livesRef.current[info.id]
      }
      const term = new XTerm({
        cursorBlink: true,
        cursorStyle: 'bar',
        fontSize: 11,
        lineHeight: 1.35,
        letterSpacing: 0,
        fontFamily:
          '"SF Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        theme: buildTerminalTheme(darkRef.current),
        // T4: PTYs always emit `\r\n` correctly — enabling `convertEol`
        // makes xterm re-convert `\n` to `\r\n`, so any stray LF becomes
        // `\r\r\n` which stacks the cursor down a line per echo. This
        // is the root cause of the "one character per line" input bug
        // when using fish/zsh inside the pane.
        convertEol: false,
        allowTransparency: false,
        scrollback: 5000,
        smoothScrollDuration: 0
      })
      term.attachCustomKeyEventHandler(event => {
        if (event.type !== 'keydown') return true
        const key = event.key.toLowerCase()

        if (
          event.shiftKey &&
          key === 'c' &&
          (event.metaKey || event.ctrlKey) &&
          term.hasSelection()
        ) {
          void copyText(term.getSelection())
          return false
        }

        if (event.ctrlKey && !event.metaKey && !event.altKey) {
          if (
            (key.length === 1 && /[a-z0-9[\];',./\\=-`]/.test(key)) ||
            [
              'backspace',
              'delete',
              'enter',
              'tab',
              'arrowup',
              'arrowdown',
              'arrowleft',
              'arrowright',
              'home',
              'end',
              'pageup',
              'pagedown'
            ].includes(key)
          ) {
            event.preventDefault()
          }
        }

        if (event.metaKey && !event.altKey && key === 'w') {
          event.preventDefault()
        }

        return true
      })
      const fit = new FitAddon()
      term.loadAddon(fit)
      const live: LiveTerminal = {
        info,
        term,
        fit,
        socket: null,
        container: null,
        disposed: false,
        opened: false,
        // T4: -1/-1 forces the first real send. Any subsequent
        // updatePtySession call with the same (cols, rows) is skipped.
        lastSentCols: -1,
        lastSentRows: -1,
        pendingResize: null
      }
      livesRef.current[info.id] = live

      live.term.onData(data => {
        if (live.socket?.readyState === WebSocket.OPEN) {
          live.socket.send(data)
        }
      })

      // T4: dedupe + sanity clamp del onResize automático de xterm.
      //
      // Dos protecciones:
      //  (a) Ignorar valores sospechosos. Bug conocido de FitAddon
      //      (xterm.js issue #5320, #4338, #4841): `proposeDimensions()`
      //      puede devolver `cols=1` intermitentemente cuando el CSS
      //      del contenedor cambia en el mismo frame que el keypress
      //      (Ink/React TUI de Claude Code dispara re-render en cada
      //      tecla). Enviar `cols=1` al PTY hace que Claude re-layoutee
      //      con 1 columna — cada carácter en su propia línea.
      //  (b) Deduplicar (cols, rows) contra `lastSentCols/Rows` — xterm
      //      dispara onResize en reflows internos que no cambian el
      //      tamaño externo. Cada envío emite SIGWINCH y fish/zsh
      //      re-renderean el prompt, dañando el input.
      live.term.onResize(({ cols, rows }) => {
        if (cols < 10 || rows < 3) return
        if (cols === live.lastSentCols && rows === live.lastSentRows) return
        live.lastSentCols = cols
        live.lastSentRows = rows
        // FAS-107 · Fase 1j · debounce 50ms: reflows CSS disparan
        // onResize múltiples veces en un mismo frame. Sin coalescer,
        // el shell recibe SIGWINCH en ráfaga y re-renderea el prompt
        // varias veces perdiendo scrollback (bug latente relacionado
        // al task #133). Con debounce, solo el último tamaño estable
        // llega al PTY.
        if (live.pendingResize !== null) {
          clearTimeout(live.pendingResize)
        }
        live.pendingResize = setTimeout(() => {
          live.pendingResize = null
          if (live.disposed) return
          void client.updatePtySession(sessionId, info.id, { cols, rows })
        }, 50)
      })

      return live
    },
    [client, sessionId]
  )

  const ensureSocket = useCallback(
    (live: LiveTerminal) => {
      if (live.disposed || live.socket) return
      const socket = new WebSocket(
        client.ptyConnectUrl(sessionId, live.info.id)
      )
      socket.binaryType = 'arraybuffer'
      live.socket = socket

      socket.addEventListener('open', () => {
        if (live.disposed) return
        try {
          // T4: NO llamar `fit.fit()` directamente — su cálculo interno
          // puede devolver cols=1 (bug conocido de FitAddon, xterm.js
          // #5320) y aplicarlo al terminal antes de que podamos
          // interceptar. En su lugar: propose primero, validar, y solo
          // aplicar `term.resize` si las dimensiones son razonables.
          const dims = live.fit.proposeDimensions()
          if (dims && dims.cols >= 10 && dims.rows >= 3) {
            live.term.resize(dims.cols, dims.rows)
            if (
              dims.cols !== live.lastSentCols ||
              dims.rows !== live.lastSentRows
            ) {
              live.lastSentCols = dims.cols
              live.lastSentRows = dims.rows
              void client.updatePtySession(sessionId, live.info.id, {
                cols: dims.cols,
                rows: dims.rows
              })
            }
          }
        } catch {
          // ignore fit failures
        }
        window.setTimeout(() => {
          if (live.disposed || live.socket?.readyState !== WebSocket.OPEN) return
          const line = live.term.buffer.active.getLine(0)
          const text = line?.translateToString(true).trim() ?? ''
          if (!text) {
            live.socket.send('\x0c')
          }
        }, 80)
      })

      socket.addEventListener('message', event => {
        if (live.disposed) return
        if (typeof event.data === 'string') {
          live.term.write(event.data)
        } else {
          live.term.write(new Uint8Array(event.data as ArrayBuffer))
        }
        // FAS-107 GF9: any output that lands while the terminal is NOT
        // the active pane (i.e. its URL is not the current one) counts
        // as unseen activity. The chip and sidebar row render an orange
        // dot; the terminal clears its own entry when it becomes active.
        const currentPath =
          typeof window !== 'undefined' ? window.location.pathname : ''
        if (!currentPath.endsWith(`/terminals/${sessionId}`)) {
          markTerminalActivity(sessionId)
        }
      })

      socket.addEventListener('close', () => {
        if (live.disposed) return
        live.term.writeln('\r\n\x1b[90m[terminal disconnected]\x1b[0m')
      })
    },
    [client, sessionId]
  )

  const mountActive = useCallback(
    (ptyId: string | null) => {
      if (!ptyId) return
      const host = hostsRef.current[ptyId]
      const live = livesRef.current[ptyId]
      if (!host || !live || live.disposed) return
      if (!live.opened) {
        live.term.open(host)
        live.container = host
        live.opened = true
      }
      // FAS-107 W1: NO se re-parenta cuando `live.container !== host`.
      // Los terminales first-class ahora viven en un portal (ver
      // terminal-layer/) — su host DOM nunca cambia mientras el terminal
      // existe. Este hook queda para uso legacy multi-shell (workspace
      // side-panel, integrations, onboarding) donde el remount sí puede
      // pasar pero es aceptable perder el buffer.
      ensureSocket(live)
      requestAnimationFrame(() => {
        try {
          // R1 fix: si el host todavía no tiene tamaño (layout aún no
          // resuelto — pasa cuando el terminal se monta como pane dentro
          // de un split), NO fittear con cols=1. El ResizeObserver que
          // vive en TerminalPanel dispara mountActive de nuevo apenas el
          // host cambie de tamaño.
          if (host.clientWidth < 10 || host.clientHeight < 10) return
          // T4: propose + validar ANTES de aplicar. `fit.fit()` puede
          // aplicar cols=1 al buffer local si `proposeDimensions()`
          // devuelve mal (xterm.js #5320). Usar el propose y aplicar
          // via `term.resize()` solo cuando las dims son razonables.
          const dims = live.fit.proposeDimensions()
          if (dims && dims.cols >= 10 && dims.rows >= 3) {
            live.term.resize(dims.cols, dims.rows)
          }
          const active = document.activeElement
          const focusOutside =
            active instanceof HTMLElement &&
            active !== document.body &&
            !host.contains(active)
          if (!renameIdRef.current && !focusOutside) {
            live.term.focus()
          }
          if (
            dims &&
            dims.cols >= 10 &&
            dims.rows >= 3 &&
            live.socket?.readyState === WebSocket.OPEN &&
            (dims.cols !== live.lastSentCols || dims.rows !== live.lastSentRows)
          ) {
            live.lastSentCols = dims.cols
            live.lastSentRows = dims.rows
            void client.updatePtySession(sessionId, live.info.id, {
              cols: dims.cols,
              rows: dims.rows
            })
          }
        } catch {
          // ignore
        }
      })
    },
    [client, ensureSocket, renameIdRef, sessionId]
  )

  const sendCommandToLive = useCallback(
    (live: LiveTerminal, command: string) => {
      const payload = command.endsWith('\n') ? command : `${command}\n`
      const send = () => {
        if (live.disposed) return
        if (live.socket?.readyState === WebSocket.OPEN) {
          live.socket.send(payload)
        }
      }
      if (live.socket?.readyState === WebSocket.OPEN) {
        send()
        return
      }
      ensureSocket(live)
      const socket = live.socket
      if (!socket) return
      if (socket.readyState === WebSocket.OPEN) {
        send()
        return
      }
      const onOpen = () => {
        socket.removeEventListener('open', onOpen)
        send()
      }
      socket.addEventListener('open', onOpen)
    },
    [ensureSocket]
  )

  const disposeAll = useCallback(() => {
    for (const ptyId of Object.keys(livesRef.current)) {
      disposeLive(ptyId)
    }
  }, [disposeLive])

  return {
    hostsRef,
    livesRef,
    connectLive,
    disposeLive,
    disposeAll,
    mountActive,
    sendCommandToLive
  }
}
