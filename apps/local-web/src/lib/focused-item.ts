/**
 * FAS-107 · Fix pre-fase1 · fuente única del ítem con foco visible.
 *
 * Antes, `TerminalPortalHost` deducía "¿este terminal está en foco?"
 * comparando `window.location.pathname.endsWith('/terminals/{id}')`.
 * Ese check falla cuando el terminal vive dentro de un group split:
 * la URL apunta al group (`/agents/{groupId}`), no al terminal. El
 * host marcaba actividad aunque el usuario estuviera mirando ese
 * pane.
 *
 * En su lugar, `App.tsx` ya calcula `effectiveSessionId` que respeta
 * `activeGroup.activeChatId` cuando hay split, y `route.sessionId`
 * cuando no. Este módulo expone ese valor globalmente para que
 * cualquier componente (empezando por `TerminalPortalHost`) pueda
 * consultarlo sin prop drilling — mismo patrón que `session-attention`.
 */

let currentFocusedItemId: string | null = null

export function setFocusedItemId(id: string | null): void {
  currentFocusedItemId = id
}

export function getFocusedItemId(): string | null {
  return currentFocusedItemId
}
