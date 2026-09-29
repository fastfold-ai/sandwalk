/**
 * FAS-107 · Fase 1f · resolver de ubicación para chats y terminales.
 *
 * Dado un `itemId` (chat o terminal) y la lista actual de tab groups,
 * determina exactamente **cómo** abrir/enfocar ese ítem:
 *
 * - Si vive **solo** (no pertenece a ningún split), basta con navegar a
 *   su ruta directa (`sessionRoutePath`) — el strip resalta el tab.
 * - Si vive **dentro de un split**, hay que navegar al ruta del grupo
 *   **y** setear `activeChatId = itemId` en ese grupo — así el pane del
 *   ítem queda en foco visible dentro del split.
 *
 * Usado por el handler de click en notificaciones nativas de macOS
 * (`onAction` del plugin de Tauri) para llevar al usuario al pane
 * exacto — cero adivinación aunque el chat/terminal viva dentro de un
 * group split anidado.
 *
 * Puro / sin side effects. La navegación real y la mutación del
 * `activeChatId` viven en el caller.
 */

import type { SessionGroup } from '@sandwalk/agent-ui-core'

import { sessionRoutePath } from '@/lib/draft-agent'

export type ItemLocation =
  | {
      kind: 'standalone'
      /** Ruta a la que navegar directamente. */
      routePath: string
    }
  | {
      kind: 'split-child'
      /** Group que contiene al ítem. */
      groupId: string
      /** Ruta a la que navegar (siempre `/agents/{groupId}`). */
      routePath: string
      /** Id a setear como `activeChatId` del group para enfocar el pane. */
      activeChatId: string
    }

export function resolveItemLocation(
  itemId: string,
  tabGroups: readonly SessionGroup[]
): ItemLocation {
  for (const group of tabGroups) {
    if (group.itemIds.includes(itemId)) {
      return {
        kind: 'split-child',
        groupId: group.id,
        routePath: sessionRoutePath(group.id),
        activeChatId: itemId
      }
    }
  }
  return {
    kind: 'standalone',
    routePath: sessionRoutePath(itemId)
  }
}
