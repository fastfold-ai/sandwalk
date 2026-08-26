import type { SessionGroup } from '@sandwalk/agent-ui-core'

/**
 * FAS-107 X5.1 · Fuente única de verdad para "qué está activo en el strip".
 *
 * Antes cada consumidor duplicaba `route.sessionId ?? route.terminalId ?? null`
 * y era fácil olvidarse de un tipo. Este es el pattern que produjo el bug
 * de "el último terminal no se cierra" (hotfix `8f38fa9`) — hubo un
 * consumidor (`stripSessionId` en App.tsx) que se olvidó de `route.terminalId`.
 *
 * Ahora todos los consumidores leen desde acá. Si en el futuro agregamos
 * un tipo nuevo (`note`, `canvas`, `mcp`, `file`), se agrega la rama en
 * este archivo y el resto se actualiza automáticamente.
 *
 * Reglas de prioridad:
 * 1. Si hay un grupo activo (split), el active del strip ES el grupo.
 *    Su chip es el resaltado, aunque adentro haya un chat/terminal activo.
 * 2. Si la ruta es `/terminals/:id`, el active es el terminal.
 * 3. Si la ruta es `/agents/:id` con un chat, el active es el chat.
 * 4. En cualquier otra ruta (draft, home, etc), null.
 */

export type StripActive =
  | { id: string; kind: 'chat' }
  | { id: string; kind: 'terminal' }
  | { id: string; kind: 'group' }

export type StripActiveKind = StripActive['kind']

type RouteLike = {
  sessionId: string | null
  terminalId: string | null
}

export function resolveStripActive(
  route: RouteLike,
  activeGroup: SessionGroup | null
): StripActive | null {
  if (activeGroup) {
    return { id: activeGroup.id, kind: 'group' }
  }
  if (route.terminalId) {
    return { id: route.terminalId, kind: 'terminal' }
  }
  if (route.sessionId) {
    // Un `sessionId` con prefijo `grp_` ya debería haber sido interceptado
    // como `activeGroup`; si aparece acá es un edge case del router.
    if (route.sessionId.startsWith('grp_')) {
      return { id: route.sessionId, kind: 'group' }
    }
    return { id: route.sessionId, kind: 'chat' }
  }
  return null
}

/** Solo el id (para consumidores que no necesitan el `kind`). */
export function resolveStripActiveId(
  route: RouteLike,
  activeGroup: SessionGroup | null
): string | null {
  return resolveStripActive(route, activeGroup)?.id ?? null
}
