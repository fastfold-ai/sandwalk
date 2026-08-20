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
}

export function useTerminalLive({
  client,
  sessionId,
  renameIdRef
}: {
  client: LocalAgentClient
  sessionId: string
  renameIdRef: RefObject<string | null>
}) {
  const hostsRef = useRef<Record<string, HTMLDivElement | null>>({})
  const livesRef = useRef<Record<string, LiveTerminal>>({})
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

  const disposeLive = useCallback((ptyId: string) => {
    const live = livesRef.current[ptyId]
    if (!live || live.disposed) return
    live.disposed = true
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
        lastSentRows: -1
      }
      livesRef.current[info.id] = live

      live.term.onData(data => {
        if (live.socket?.readyState === WebSocket.OPEN) {
          live.socket.send(data)
        }
      })

      // T4: dedupe onResize. xterm dispara este handler durante reflows
      // internos aunque las dimensiones externas no hayan cambiado —
      // cada send emite SIGWINCH y fish/zsh re-renderean el prompt,
      // rompiendo el input visible. Solo enviamos si (cols, rows)
      // realmente cambió desde el último send.
      live.term.onResize(({ cols, rows }) => {
        if (cols === live.lastSentCols && rows === live.lastSentRows) return
        live.lastSentCols = cols
        live.lastSentRows = rows
        void client.updatePtySession(sessionId, info.id, { cols, rows })
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
          live.fit.fit()
          const dims = live.fit.proposeDimensions()
          if (
            dims &&
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
        host.replaceChildren()
        live.term.open(host)
        live.container = host
        live.opened = true
      }
      ensureSocket(live)
      requestAnimationFrame(() => {
        try {
          // R1 fix: si el host todavía no tiene tamaño (layout aún no
          // resuelto — pasa cuando el terminal se monta como pane dentro
          // de un split), NO fittear con cols=1. El ResizeObserver que
          // vive en TerminalPanel dispara mountActive de nuevo apenas el
          // host cambie de tamaño. Enviar cols=1 al PTY hace que el shell
          // escriba cada carácter en una línea nueva y el buffer queda
          // así aunque el fit posterior corrija.
          if (host.clientWidth < 10 || host.clientHeight < 10) return
          live.fit.fit()
          const active = document.activeElement
          const focusOutside =
            active instanceof HTMLElement &&
            active !== document.body &&
            !host.contains(active)
          if (!renameIdRef.current && !focusOutside) {
            live.term.focus()
          }
          const dims = live.fit.proposeDimensions()
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
