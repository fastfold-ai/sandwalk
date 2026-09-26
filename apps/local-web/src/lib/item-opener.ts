/**
 * FAS-107 · Fase 1f · bridge global para "abrir un ítem por su id".
 *
 * Usado por el handler de click de notificaciones nativas macOS y por
 * cualquier módulo que vive fuera del árbol React donde vive `navigate`
 * (React Router) y `setTabGroupActiveChat` (viene del hook
 * `useAppTabGroups`). Mismo patrón singleton que `focused-item.ts`:
 * App.tsx inyecta al mount una función que sabe navegar + setear el
 * pane activo del split usando el resolver; el resto del código
 * consulta `openItem(itemId)` sin preocuparse de por debajo.
 */

let opener: ((itemId: string) => void) | null = null

export function setItemOpener(fn: ((itemId: string) => void) | null): void {
  opener = fn
}

export function openItem(itemId: string): void {
  if (opener === null) return
  opener(itemId)
}
