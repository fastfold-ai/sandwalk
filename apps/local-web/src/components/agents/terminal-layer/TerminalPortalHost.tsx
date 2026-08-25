import '@xterm/xterm/css/xterm.css'

import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { FitAddon } from '@xterm/addon-fit'
import { Terminal as XTerm } from '@xterm/xterm'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { markTerminalActivity } from '@/lib/terminal-attention'
import {
  buildTerminalTheme,
  isDocumentDark,
  watchTerminalTheme
} from '@/lib/terminal-theme'

import { useTerminalLayer } from './terminal-layer-registry'

/**
 * FAS-107 W1: renderea el xterm de UN terminal en el layer flotante.
 *
 * Este componente vive fuera del árbol de layout (via `createPortal`
 * al `TerminalLayerRoot`). El xterm se monta una única vez y se
 * mantiene mientras exista el terminal — no se destruye cuando el
 * usuario cambia de tab / split / vista.
 *
 * Sincronización con el `TerminalPlaceholder`:
 *   - Consulta el registry para saber si hay un placeholder para
 *     este `terminalId`.
 *   - Si lo hay: calcula `getBoundingClientRect()` del placeholder y
 *     aplica `position: fixed; top/left/width/height` para calzar.
 *   - Si no lo hay: `display: none`.
 *   - `ResizeObserver` sobre el placeholder + listener de scroll +
 *     resize de window para re-posicionar en cada cambio, debounced
 *     con `requestAnimationFrame`.
 */

type PtyInfo = {
  id: string
  session_id: string
  title: string
}

export function TerminalPortalHost({
  client,
  terminalId
}: {
  client: LocalAgentClient
  terminalId: string
}) {
  const registry = useTerminalLayer()
  const layerRoot = registry.getLayerRoot()

  // W3: el host DIV se guarda como state (no useRef) para que el
  // `useEffect` que monta el xterm pueda depender del nodo real y
  // re-ejecutarse cuando el div aparezca (segundo tick, después de
  // que llegó el layerRoot). Antes tenía deps [] y corría con host=null
  // → el xterm nunca se montaba.
  const [hostNode, setHostNode] = useState<HTMLDivElement | null>(null)
  const hostRef = useRef<HTMLDivElement | null>(null)
  hostRef.current = hostNode
  const termRef = useRef<XTerm | null>(null)
  const fitRef = useRef<FitAddon | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const ptyRef = useRef<PtyInfo | null>(null)
  const lastDimsRef = useRef<{ cols: number; rows: number }>({
    cols: -1,
    rows: -1
  })
  // `layerVersion` fuerza un re-render cuando el placeholder cambia.
  // Solo lo usamos para gatillar reconciliación (React ejecuta de nuevo
  // el `createPortal` con el layerRoot fresco).
  const [, setLayerVersion] = useState(0)

  // Suscribirse a cambios del placeholder: muestra/oculta y re-posiciona.
  useEffect(() => {
    const listener = () => {
      setLayerVersion(v => v + 1)
      schedulePosition()
    }
    const unsub = registry.subscribe(terminalId, listener)
    return unsub
    // schedulePosition se declara abajo — la ref indirecta funciona
    // porque el listener se resuelve en tiempo de invocación.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [registry, terminalId])

  // Posicionamiento debounced con rAF.
  const rafRef = useRef<number | null>(null)
  const schedulePosition = () => {
    if (rafRef.current != null) return
    rafRef.current = window.requestAnimationFrame(() => {
      rafRef.current = null
      applyPosition()
    })
  }

  const applyPosition = () => {
    const host = hostRef.current
    if (!host) return
    const entry = registry.getPlaceholder(terminalId)
    if (!entry || !entry.node.isConnected) {
      host.style.display = 'none'
      return
    }
    const rect = entry.node.getBoundingClientRect()
    if (rect.width < 1 || rect.height < 1) {
      host.style.display = 'none'
      return
    }
    host.style.display = ''
    host.style.position = 'fixed'
    host.style.top = `${rect.top}px`
    host.style.left = `${rect.left}px`
    host.style.width = `${rect.width}px`
    host.style.height = `${rect.height}px`
    host.style.pointerEvents = 'auto'
    // Refit xterm al nuevo tamaño y notificar al PTY.
    const fit = fitRef.current
    const term = termRef.current
    if (!fit || !term) return
    try {
      const dims = fit.proposeDimensions()
      if (dims && dims.cols >= 10 && dims.rows >= 3) {
        term.resize(dims.cols, dims.rows)
        if (
          (dims.cols !== lastDimsRef.current.cols ||
            dims.rows !== lastDimsRef.current.rows) &&
          socketRef.current?.readyState === WebSocket.OPEN &&
          ptyRef.current
        ) {
          lastDimsRef.current = { cols: dims.cols, rows: dims.rows }
          void client.updatePtySession(terminalId, ptyRef.current.id, {
            cols: dims.cols,
            rows: dims.rows
          })
        }
      }
    } catch {
      // ignore — cualquier miscálculo del fit se corrige en el siguiente frame
    }
  }

  // W3: montar xterm cuando el `hostNode` esté disponible. Antes esto
  // dependía de `[]` y corría en el primer commit, momento en el que
  // `layerRoot` aún era null → el portal no rendereaba el div → el
  // host estaba en null → xterm nunca se montaba. Ahora depende del
  // nodo real, que puede aparecer en el segundo tick.
  useEffect(() => {
    const host = hostNode
    if (!host || termRef.current) return

    const term = new XTerm({
      cursorBlink: true,
      cursorStyle: 'bar',
      fontSize: 11,
      lineHeight: 1.35,
      letterSpacing: 0,
      fontFamily:
        '"SF Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
      theme: buildTerminalTheme(isDocumentDark()),
      // El PTY ya emite CRLF — no convertir localmente para evitar
      // el bug de "un caracter por línea" que veníamos peleando.
      convertEol: false,
      allowTransparency: false,
      scrollback: 5000,
      smoothScrollDuration: 0
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(host)
    termRef.current = term
    fitRef.current = fit

    // Reflejo de theme dark/light.
    const stopThemeWatch = watchTerminalTheme(() => {
      term.options.theme = buildTerminalTheme(isDocumentDark())
    })

    // Enviar keystrokes al backend via WS.
    term.onData(data => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(data)
      }
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
        void client.updatePtySession(terminalId, ptyRef.current.id, {
          cols,
          rows
        })
      }
    })

    // Crear/reusar PTY del backend.
    let cancelled = false
    ;(async () => {
      try {
        const existing = await client.listPtySessions(terminalId)
        if (cancelled) return
        const info =
          existing[0] ??
          (await client.createPtySession(terminalId))
        if (cancelled) return
        ptyRef.current = info as PtyInfo
        const ws = new WebSocket(client.ptyConnectUrl(terminalId, info.id))
        ws.binaryType = 'arraybuffer'
        socketRef.current = ws
        ws.onopen = () => {
          if (cancelled) return
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
            term.write(event.data)
          } else {
            term.write(new Uint8Array(event.data as ArrayBuffer))
          }
          const path =
            typeof window !== 'undefined' ? window.location.pathname : ''
          if (!path.endsWith(`/terminals/${terminalId}`)) {
            markTerminalActivity(terminalId)
          }
        }
        ws.onclose = () => {
          if (cancelled) return
          term.writeln('\r\n\x1b[90m[terminal disconnected]\x1b[0m')
        }
      } catch (err) {
        if (!cancelled) {
          console.error('TerminalPortalHost boot failed', err)
        }
      }
    })()

    // Reposicionamiento en window resize + scroll.
    const onWindow = () => schedulePosition()
    window.addEventListener('resize', onWindow)
    window.addEventListener('scroll', onWindow, { capture: true })

    // FAS-107 X3 Fase 7: un solo `ResizeObserver` por sesión. Antes se
    // hacía `observer.disconnect()` + `registerObserver()` en cada
    // notify del registry — sin razón real (el observer sigue apuntando
    // al mismo nodo si el placeholder no cambió). Ese ciclo dejaba
    // ventanas cortas sin observer activo, y cuando el user
    // redimensionaba el split justo en ese frame, el xterm quedaba
    // desalineado hasta el próximo scroll/resize de window.
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

    // Foco: cuando el user clickea el host, avisar al placeholder para
    // que el split actualice su activeChatId.
    const onMouseDown = () => {
      const entry = registry.getPlaceholder(terminalId)
      entry?.onFocus()
    }
    host.addEventListener('mousedown', onMouseDown)

    // Posición inicial.
    schedulePosition()

    return () => {
      cancelled = true
      unsubObserver()
      observer.disconnect()
      window.removeEventListener('resize', onWindow)
      window.removeEventListener('scroll', onWindow, { capture: true })
      host.removeEventListener('mousedown', onMouseDown)
      stopThemeWatch()
      if (rafRef.current != null) {
        window.cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      try {
        socketRef.current?.close()
      } catch {
        // ignore
      }
      try {
        term.dispose()
      } catch {
        // ignore
      }
      termRef.current = null
      fitRef.current = null
      socketRef.current = null
      ptyRef.current = null
    }
    // Deps: [hostNode] — el effect corre cuando el div del portal
    // aparece por primera vez (después de que layerRoot llegó). Los
    // otros valores (client, terminalId, registry) son estables por
    // instancia — no hace falta re-crear el xterm si cambian.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hostNode])

  if (!layerRoot) return null

  return createPortal(
    <div
      ref={setHostNode}
      data-terminal-portal-host={terminalId}
      // Oculto por default hasta que applyPosition corra la primera vez.
      style={{ display: 'none' }}
    />,
    layerRoot
  )
}
