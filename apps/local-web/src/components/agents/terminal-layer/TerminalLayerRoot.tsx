import { useLayoutEffect, useRef } from 'react'

import { useTerminalLayer } from './terminal-layer-registry'

/**
 * FAS-107 W1/W2: contenedor absoluto donde el portal renderea los
 * `TerminalPortalHost`.
 *
 * Vive dentro del área "main" de la app, cubre todo el viewport del
 * main con `inset-0` y `pointer-events: none` en el root — los hosts
 * individuales llevan `pointer-events: auto` para recibir input del
 * terminal. Así los eventos de mouse que caen en zonas donde no hay
 * terminal atraviesan el layer y llegan al chat / sidebar / lo que
 * esté debajo.
 *
 * z-index: 30 — por ENCIMA del contenido normal del main (chat,
 * splits, headers, panels) pero por DEBAJO de cualquier menú/dropdown
 * Radix (z-50+). Si estuviera en z-0, el content div que va después
 * en el DOM lo taparía completamente (bug W2). En modo mac-glass el
 * sandwalk-shell-main crea contexto de apilamiento con z-index:2 —
 * el layer necesita valor alto para pintarse ARRIBA de sus siblings.
 */
export function TerminalLayerRoot() {
  const registry = useTerminalLayer()
  const nodeRef = useRef<HTMLDivElement | null>(null)

  // W3: `useLayoutEffect` corre ANTES del paint y ANTES de los
  // `useEffect` normales. Así el layerRoot queda registrado antes de
  // que los `TerminalPortalHost` que viven como siblings intenten
  // consultarlo — sin esto los hosts terminaban con `layerRoot=null`
  // durante todo su primer commit y su xterm nunca se montaba.
  useLayoutEffect(() => {
    registry.setLayerRoot(nodeRef.current)
    return () => {
      registry.setLayerRoot(null)
    }
  }, [registry])

  return (
    <div
      ref={nodeRef}
      aria-hidden
      className="pointer-events-none absolute inset-0 z-30"
    />
  )
}
