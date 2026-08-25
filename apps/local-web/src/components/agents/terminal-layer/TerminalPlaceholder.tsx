import { useEffect, useRef } from 'react'

import { useTerminalLayer } from './terminal-layer-registry'

/**
 * FAS-107 W1: reserva el hueco donde el `TerminalPortalHost` va a
 * posicionar su xterm.
 *
 * Es un div vacío del árbol React que:
 *   - Registra su `ref` al `TerminalLayerRegistry` con el `terminalId`.
 *   - Reserva el ESPACIO en el layout normal (el contenedor padre lo
 *     dimensiona con flex/grid como cualquier otro div — h-full, flex-1,
 *     lo que sea que el sitio quiera).
 *   - No pinta nada. El terminal se pinta ENCIMA vía el layer flotante.
 *
 * El `onFocus` se dispara cuando el usuario clickea el terminal
 * flotante (el portal host lo llama). Sirve para actualizar el
 * `activeChatId` del split cuando el pane del terminal recibe foco.
 */
export function TerminalPlaceholder({
  terminalId,
  onFocus,
  onContextMenu,
  className
}: {
  terminalId: string
  onFocus?: () => void
  /**
   * FAS-107 X4.2: se dispara cuando el user hace click derecho sobre
   * el xterm flotante. El `TerminalPortalHost` reenvía el evento hasta
   * acá vía el registry, para que el ancestro React (el pane del
   * split) pueda pintar el menú contextual.
   */
  onContextMenu?: (event: MouseEvent) => void
  className?: string
}) {
  const registry = useTerminalLayer()
  const nodeRef = useRef<HTMLDivElement | null>(null)
  const onFocusRef = useRef(onFocus)
  onFocusRef.current = onFocus
  const onContextMenuRef = useRef(onContextMenu)
  onContextMenuRef.current = onContextMenu

  useEffect(() => {
    const node = nodeRef.current
    if (!node) return
    const unregister = registry.registerPlaceholder(terminalId, {
      node,
      onFocus: () => onFocusRef.current?.(),
      onContextMenu: event => onContextMenuRef.current?.(event)
    })
    return unregister
  }, [registry, terminalId])

  // El div ocupa el espacio con `h-full w-full` (o lo que el caller
  // ponga). El terminal real se posiciona encima via el layer.
  return <div ref={nodeRef} className={className ?? 'h-full w-full'} />
}
