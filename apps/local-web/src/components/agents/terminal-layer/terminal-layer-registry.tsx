import { createContext, useContext, useMemo, useRef, useState } from 'react'

/**
 * FAS-107 W1: Portal-based terminal rendering.
 *
 * El "layer registry" es el punto de encuentro entre dos partes:
 *
 *   1. Los `<TerminalPlaceholder>` que viven DENTRO del árbol React
 *      (dentro de un split, en la ruta `/terminals/:id`, etc.) y le
 *      dicen al registry "acá va el terminal X".
 *
 *   2. Los `<TerminalPortalHost>` que viven en el layer flotante
 *      (via `createPortal`) y consultan el registry para saber en qué
 *      lugar del viewport tienen que posicionar su xterm.
 *
 * De esta forma el xterm NUNCA es dueño de un div dentro del árbol de
 * componentes React — se mueve como una "calcomanía" siguiendo al
 * placeholder que le corresponde. React reconcile normal, xterm hace
 * lo suyo, no se pisan.
 */

export type PlaceholderEntry = {
  node: HTMLDivElement
  onFocus: () => void
  /**
   * FAS-107 X3 Fase 5: contextmenu del xterm. El `TerminalPortalHost`
   * lo llama cuando el user hace click derecho sobre el layer. Sin
   * esto, el evento nunca llega al `TerminalLeaf` (que vive en otro
   * árbol React que el portal), y el menú del pane no aparece.
   */
  onContextMenu?: (event: MouseEvent) => void
}

export type TerminalLayerRegistry = {
  /** Elemento DOM raíz donde el portal renderea los layers. */
  getLayerRoot: () => HTMLDivElement | null
  setLayerRoot: (node: HTMLDivElement | null) => void
  /**
   * Registra el placeholder de un terminal. Retorna la función de
   * desregistro para llamar en el cleanup del `useEffect`.
   */
  registerPlaceholder: (
    terminalId: string,
    entry: PlaceholderEntry
  ) => () => void
  getPlaceholder: (terminalId: string) => PlaceholderEntry | null
  /**
   * Suscribe un listener que se dispara cuando el placeholder del
   * terminal indicado cambia (registrado o desregistrado). Es lo que
   * el `TerminalPortalHost` usa para saber cuándo re-posicionarse o
   * cuándo ocultarse.
   */
  subscribe: (terminalId: string, listener: () => void) => () => void
}

const TerminalLayerContext = createContext<TerminalLayerRegistry | null>(null)

export function useTerminalLayer(): TerminalLayerRegistry {
  const ctx = useContext(TerminalLayerContext)
  if (!ctx) {
    throw new Error(
      'useTerminalLayer must be used inside <TerminalLayerProvider>'
    )
  }
  return ctx
}

export function TerminalLayerProvider({
  children
}: {
  children: React.ReactNode
}) {
  const layerRootRef = useRef<HTMLDivElement | null>(null)
  // Version state: fuerza re-render de consumidores cuando layerRoot cambia.
  const [, setLayerRootVersion] = useState(0)

  const placeholdersRef = useRef(new Map<string, PlaceholderEntry>())
  const listenersRef = useRef(new Map<string, Set<() => void>>())

  const registry = useMemo<TerminalLayerRegistry>(() => {
    const notifyListeners = (terminalId: string) => {
      const set = listenersRef.current.get(terminalId)
      if (!set) return
      for (const listener of set) listener()
    }

    return {
      getLayerRoot: () => layerRootRef.current,
      setLayerRoot: node => {
        if (layerRootRef.current === node) return
        layerRootRef.current = node
        // Re-renderiza consumidores para que el `createPortal` reciba
        // el nodo actualizado (o null si el root se desmontó).
        setLayerRootVersion(v => v + 1)
      },
      registerPlaceholder: (terminalId, entry) => {
        placeholdersRef.current.set(terminalId, entry)
        notifyListeners(terminalId)
        return () => {
          const current = placeholdersRef.current.get(terminalId)
          // Solo desregistrar si el entry es el mismo — evita que
          // un placeholder viejo desregistre al nuevo cuando dos
          // placeholders alternan por race de re-mount de React.
          if (current && current.node === entry.node) {
            placeholdersRef.current.delete(terminalId)
            notifyListeners(terminalId)
          }
        }
      },
      getPlaceholder: terminalId => {
        return placeholdersRef.current.get(terminalId) ?? null
      },
      subscribe: (terminalId, listener) => {
        let set = listenersRef.current.get(terminalId)
        if (!set) {
          set = new Set()
          listenersRef.current.set(terminalId, set)
        }
        set.add(listener)
        return () => {
          const current = listenersRef.current.get(terminalId)
          if (!current) return
          current.delete(listener)
          if (current.size === 0) {
            listenersRef.current.delete(terminalId)
          }
        }
      }
    }
  }, [])

  return (
    <TerminalLayerContext.Provider value={registry}>
      {children}
    </TerminalLayerContext.Provider>
  )
}
