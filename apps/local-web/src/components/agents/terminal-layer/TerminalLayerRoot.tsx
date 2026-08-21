import { useEffect, useRef } from 'react'

import { useTerminalLayer } from './terminal-layer-registry'

/**
 * FAS-107 W1: contenedor absoluto donde el portal renderea los
 * `TerminalPortalHost`.
 *
 * Vive dentro del área "main" de la app, cubre todo el viewport del
 * main con `inset-0` y `pointer-events: none` en el root — los hosts
 * individuales llevan `pointer-events: auto` para recibir input del
 * terminal. Así los eventos de mouse que caen en zonas donde no hay
 * terminal atraviesan el layer y llegan al chat / sidebar / lo que
 * esté debajo.
 *
 * z-index: 0 (o sin z-index explícito) — el layer se pinta ENCIMA del
 * contenido main (que renderea antes en el árbol) pero DEBAJO de
 * cualquier menú/dropdown que use portal Radix (z-50+).
 */
export function TerminalLayerRoot() {
  const registry = useTerminalLayer()
  const nodeRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    // Registra el nodo raíz una vez montado — los `TerminalPortalHost`
    // consumen `getLayerRoot()` en su primer render para elegir dónde
    // hacer `createPortal`.
    registry.setLayerRoot(nodeRef.current)
    return () => {
      registry.setLayerRoot(null)
    }
  }, [registry])

  return (
    <div
      ref={nodeRef}
      aria-hidden
      className="pointer-events-none absolute inset-0 z-0"
    />
  )
}
