import { useEffect, useState } from 'react'

/**
 * Devuelve `true` cuando la ventana es más angosta que `breakpoint` (default
 * 1280 px). Usado por el shell de split view para pasar los side panels
 * (Files / Preview / Terminal) de columna resizable a modal overlay: en un
 * layout con N chats en paralelo + un side panel al mismo tiempo, por debajo
 * de ese ancho ya no hay espacio útil para ambos.
 */
export function useIsNarrowWindow(breakpoint = 1280): boolean {
  const [narrow, setNarrow] = useState(() =>
    typeof window === 'undefined' ? false : window.innerWidth < breakpoint
  )
  useEffect(() => {
    if (typeof window === 'undefined') return
    const mq = window.matchMedia(`(max-width: ${breakpoint - 1}px)`)
    const onChange = () => setNarrow(mq.matches)
    onChange()
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [breakpoint])
  return narrow
}
