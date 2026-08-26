import type {
  AgentSession,
  PaneNode,
  SessionGroup
} from '@sandwalk/agent-ui-core'
import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useMemo
} from 'react'

import { writeTabGroups } from '@/lib/app-storage'
import { useTerminalsStore } from '@/lib/terminals-store'

/**
 * Store hook para split-view groups. A partir de la migración
 * multi-proyecto, los grupos viven en UNA lista plana única — no por
 * scope de proyecto — y se muestran en cada proyecto donde tienen al
 * menos un chat. `activeProjectId` solo se usa para decidir qué grupos
 * son visibles en el sidebar/strip/dropdown del scope actual.
 *
 * Ciclo de vida vs `openTabIds`:
 *   - createGroup([A, B, C]) saca A/B/C de openTabIds e inserta `grp_x`.
 *   - dissolveGroup(grp_x) saca `grp_x` de openTabIds y re-inserta los
 *     chats NATIVOS del scope actual (los que pertenecen al proyecto
 *     activo). Los invitados salen del grupo y vuelven libres a su
 *     proyecto natal — no se insertan como tabs en este scope.
 *   - addToGroup / removeFromGroup: análogos al patrón previo.
 *
 * `openTabIds` sigue conteniendo una MEZCLA de chat ids y group ids;
 * `isSessionGroupId(id)` desambigua.
 */

type SetOpenTabIds = (
  value: string[] | ((current: string[]) => string[])
) => void

function generateGroupId(): string {
  const rand =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID().replace(/-/g, '').slice(0, 12)
      : Math.random().toString(36).slice(2, 14)
  return `grp_${rand}`
}

/*
 * Nombre por defecto para un split recién creado: "Group N" con N libre
 * mirando todos los grupos existentes. Se recicla: si tenías Group 1, 2, 3
 * y borrás el 2, el próximo grupo se llama "Group 2". El nombre custom
 * del usuario reemplaza este auto cuando renombra.
 */
function nextAutoGroupName(existingGroups: SessionGroup[]): string {
  const used = new Set<number>()
  const re = /^Group\s+(\d+)$/
  for (const g of existingGroups) {
    const match = re.exec(g.name || '')
    if (match) used.add(Number(match[1]))
  }
  let n = 1
  while (used.has(n)) n++
  return `Group ${n}`
}

/**
 * Un grupo es visible en el scope de un proyecto cuando alguno de sus
 * chats pertenece a ese proyecto. En "All projects" (activeProjectId =
 * null) se ven todos los grupos.
 */
function groupBelongsToScope(
  group: SessionGroup,
  activeProjectId: string | null,
  chatProjectById: Map<string, string | null>,
  terminalProjectById: Map<string, string | null>
): boolean {
  if (activeProjectId === null) return true
  return group.itemIds.some(chatId => {
    if (chatId.startsWith('term_')) {
      return terminalProjectById.get(chatId) === activeProjectId
    }
    return chatProjectById.get(chatId) === activeProjectId
  })
}

export function useAppTabGroups(
  activeProjectId: string | null,
  sessions: AgentSession[],
  allTabGroups: SessionGroup[],
  setAllTabGroups: Dispatch<SetStateAction<SessionGroup[]>>,
  setOpenTabIds: SetOpenTabIds
) {
  const chatProjectById = useMemo(() => {
    const map = new Map<string, string | null>()
    for (const s of sessions) map.set(s.id, s.projectId ?? null)
    return map
  }, [sessions])

  // FAS-107 X4.4-hotfix: sub al store singleton de terminales para
  // resolver `projectId` cuando un grupo contiene `term_*`. Antes se
  // resolvía solo con `sessions` → un grupo con solo terminales o con
  // un terminal + chats de otros proyectos daba resultados incorrectos
  // en `groupBelongsToScope` y en `dissolveGroup`.
  const terminals = useTerminalsStore(state => state.terminals)
  const terminalProjectById = useMemo(() => {
    const map = new Map<string, string | null>()
    for (const t of terminals) map.set(t.id, t.projectId ?? null)
    return map
  }, [terminals])

  // Grupos visibles en el proyecto activo (por regla multi-proyecto).
  const tabGroups = useMemo(
    () =>
      allTabGroups.filter(g =>
        groupBelongsToScope(
          g,
          activeProjectId,
          chatProjectById,
          terminalProjectById
        )
      ),
    [allTabGroups, activeProjectId, chatProjectById, terminalProjectById]
  )

  const patchGroups = useCallback(
    (updater: (current: SessionGroup[]) => SessionGroup[]) => {
      setAllTabGroups(current => {
        const next = updater(current)
        if (next === current) return current
        writeTabGroups(next)
        return next
      })
    },
    [setAllTabGroups]
  )

  const createGroup = useCallback(
    (chatIds: string[], overrides?: Partial<SessionGroup>): string | null => {
      // Un grupo pending puede arrancar con 1 chat (el picker ocupa el
      // segundo panel); un grupo normal necesita al menos 2.
      const minSize = overrides?.isPending ? 1 : 2
      if (chatIds.length < minSize) return null
      const id = overrides?.id ?? generateGroupId()
      const name =
        overrides?.name && overrides.name.trim().length > 0
          ? overrides.name
          : nextAutoGroupName(allTabGroups)
      const group: SessionGroup = {
        id,
        name,
        color: overrides?.color ?? null,
        pinned: overrides?.pinned ?? false,
        chatIds,
        activeChatId: overrides?.activeChatId ?? chatIds[0],
        isPending: overrides?.isPending
      }
      patchGroups(current => [...current, group])
      setOpenTabIds(current => {
        const firstIdx = current.findIndex(tabId => chatIds.includes(tabId))
        const filtered = current.filter(tabId => !chatIds.includes(tabId))
        const insertAt = firstIdx >= 0 ? firstIdx : 0
        filtered.splice(insertAt, 0, id)
        return filtered
      })
      return id
    },
    [patchGroups, setOpenTabIds, allTabGroups]
  )

  /**
   * "Create split view" desde un chat: crea un grupo pending con ese
   * único chat. El segundo panel se pinta como picker hasta que el
   * usuario elija su compañero (ver `promotePendingGroup`) o cancele
   * (ver `dissolveGroup`).
   *
   * Antes de crear, se cancelan los pending anteriores — solo puede
   * haber uno "en armado" a la vez. Los pending son estado UI efímero;
   * dejar varios cargados confunde y ensucia la strip.
   */
  const createPendingGroup = useCallback(
    (sourceChatId: string): string | null => {
      const priorPending = allTabGroups.filter(g => g.isPending)
      if (priorPending.length > 0) {
        patchGroups(current => current.filter(g => !g.isPending))
        setOpenTabIds(current =>
          current.filter(id => !priorPending.some(g => g.id === id))
        )
      }
      return createGroup([sourceChatId], { isPending: true })
    },
    [allTabGroups, patchGroups, setOpenTabIds, createGroup]
  )

  /**
   * Cierra el estado pending del grupo: agrega el chat elegido y limpia
   * el flag. Si el chat elegido ya vive en otro grupo, se lo saca de
   * ahí primero (un chat solo puede estar en un grupo).
   */
  const promotePendingGroup = useCallback(
    (groupId: string, partnerChatId: string) => {
      patchGroups(current => {
        // Sacar partnerChatId de cualquier otro grupo donde viva.
        const scrubbed = current.map(g =>
          g.id !== groupId && g.itemIds.includes(partnerChatId)
            ? { ...g, chatIds: g.itemIds.filter(id => id !== partnerChatId) }
            : g
        )
        return scrubbed.map(g => {
          if (g.id !== groupId) return g
          const nextChatIds = g.itemIds.includes(partnerChatId)
            ? g.itemIds
            : [...g.itemIds, partnerChatId]
          return {
            ...g,
            chatIds: nextChatIds,
            isPending: false
          }
        })
      })
      setOpenTabIds(current => current.filter(id => id !== partnerChatId))
    },
    [patchGroups, setOpenTabIds]
  )

  /**
   * Dissolve: liberación del grupo.
   * - Se elimina el grupo del storage plano.
   * - En la strip del scope activo, `grp_id` se reemplaza por los chats
   *   NATIVOS del scope actual (chats cuyo projectId matchea). Los
   *   invitados no se insertan como tabs acá — quedan libres en su
   *   proyecto natal, donde ya aparecen por naturaleza.
   */
  const dissolveGroup = useCallback(
    (groupId: string) => {
      const group = allTabGroups.find(g => g.id === groupId)
      if (!group) return
      patchGroups(current => current.filter(g => g.id !== groupId))
      // FAS-107 X4.4-hotfix: `chatProjectById` solo mapea `sessions`
      // (chats). Los `term_*` en `group.itemIds` no aparecen ahí →
      // antes se filtraban fuera de `nativesInThisScope` → al dissolve,
      // el terminal survivor NO se reinsertaba en `openTabIds` →
      // desaparecía del strip aunque siguiera vivo en el sidebar.
      // Ahora resolvemos el projectId de los terminales del store
      // singleton Zustand.
      const terminals = useTerminalsStore.getState().terminals
      const nativesInThisScope = group.itemIds.filter(chatId => {
        if (activeProjectId === null) return true
        if (chatId.startsWith('term_')) {
          const term = terminals.find(t => t.id === chatId)
          return term ? (term.projectId ?? null) === activeProjectId : false
        }
        return chatProjectById.get(chatId) === activeProjectId
      })
      setOpenTabIds(current => {
        const idx = current.indexOf(groupId)
        // X4.4-hotfix: si el grupo NO estaba en el strip (dissolve
        // desde el sidebar), NO abrimos sus hijos como tabs sueltos.
        // Antes se agregaban al final "magicamente" — sorpresa fea.
        // Sólo re-abrimos cuando el chip del grupo estaba visible.
        if (idx < 0) return current
        return [
          ...current.slice(0, idx),
          ...nativesInThisScope,
          ...current.slice(idx + 1)
        ]
      })
    },
    [
      patchGroups,
      setOpenTabIds,
      allTabGroups,
      activeProjectId,
      chatProjectById
    ]
  )

  /** Add a chat to an existing group. Si el chat vive en otro grupo, se
   * remueve de ahí primero (un chat solo puede pertenecer a un grupo). */
  const addToGroup = useCallback(
    (groupId: string, chatId: string) => {
      patchGroups(current => {
        const scrubbed = current.map(g =>
          g.id === groupId
            ? g
            : g.itemIds.includes(chatId)
              ? { ...g, chatIds: g.itemIds.filter(c => c !== chatId) }
              : g
        )
        return scrubbed.map(g =>
          g.id === groupId && !g.itemIds.includes(chatId)
            ? { ...g, chatIds: [...g.itemIds, chatId] }
            : g
        )
      })
      setOpenTabIds(current => current.filter(id => id !== chatId))
    },
    [patchGroups, setOpenTabIds]
  )

  const removeFromGroup = useCallback(
    (groupId: string, chatId: string): number => {
      const group = allTabGroups.find(g => g.id === groupId)
      if (!group || !group.itemIds.includes(chatId)) return -1
      const nextIds = group.itemIds.filter(id => id !== chatId)
      const nextActive =
        group.activeChatId === chatId
          ? nextIds[0] ?? group.activeChatId
          : group.activeChatId
      patchGroups(current =>
        current.map(g =>
          g.id === groupId
            ? { ...g, chatIds: nextIds, activeChatId: nextActive }
            : g
        )
      )
      setOpenTabIds(current => {
        const groupIdx = current.indexOf(groupId)
        if (groupIdx < 0) return [...current, chatId]
        return [
          ...current.slice(0, groupIdx + 1),
          chatId,
          ...current.slice(groupIdx + 1)
        ]
      })
      return nextIds.length
    },
    [patchGroups, setOpenTabIds, allTabGroups]
  )

  const renameGroup = useCallback(
    (groupId: string, name: string) => {
      patchGroups(current =>
        current.map(g => (g.id === groupId ? { ...g, name } : g))
      )
    },
    [patchGroups]
  )

  const setGroupColor = useCallback(
    (groupId: string, color: string | null) => {
      patchGroups(current =>
        current.map(g => (g.id === groupId ? { ...g, color } : g))
      )
    },
    [patchGroups]
  )

  const setGroupPinned = useCallback(
    (groupId: string, pinned: boolean) => {
      patchGroups(current =>
        current.map(g => (g.id === groupId ? { ...g, pinned } : g))
      )
    },
    [patchGroups]
  )

  const setGroupActiveChat = useCallback(
    (groupId: string, chatId: string) => {
      patchGroups(current =>
        current.map(g =>
          g.id === groupId && g.itemIds.includes(chatId)
            ? { ...g, activeChatId: chatId }
            : g
        )
      )
    },
    [patchGroups]
  )

  const reorderChatsInGroup = useCallback(
    (groupId: string, orderedChatIds: string[]) => {
      patchGroups(current =>
        current.map(g => {
          if (g.id !== groupId) return g
          const currentSet = new Set(g.itemIds)
          const nextSet = new Set(orderedChatIds)
          if (
            currentSet.size !== nextSet.size ||
            [...currentSet].some(id => !nextSet.has(id))
          ) {
            return g
          }
          return { ...g, chatIds: orderedChatIds }
        })
      )
    },
    [patchGroups]
  )

  /**
   * Replace the tiling tree for a specific monitor fingerprint. Called on
   * every split / close / resize inside the tiling container; the layouts
   * for other monitors are left untouched.
   */
  const setGroupLayoutForMonitor = useCallback(
    (groupId: string, fingerprint: string, tree: PaneNode) => {
      patchGroups(current =>
        current.map(g => {
          if (g.id !== groupId) return g
          const prev = g.layout?.perMonitor ?? {}
          return {
            ...g,
            layout: {
              perMonitor: { ...prev, [fingerprint]: tree }
            }
          }
        })
      )
    },
    [patchGroups]
  )

  /**
   * Wipe the layout for a specific monitor — used when the user picks
   * "reset layout" or when the chat list changes so drastically that the
   * saved layout no longer maps cleanly.
   */
  const clearGroupLayoutForMonitor = useCallback(
    (groupId: string, fingerprint: string) => {
      patchGroups(current =>
        current.map(g => {
          if (g.id !== groupId || !g.layout) return g
          const next = { ...g.layout.perMonitor }
          if (!(fingerprint in next)) return g
          delete next[fingerprint]
          return { ...g, layout: { perMonitor: next } }
        })
      )
    },
    [patchGroups]
  )

  /**
   * Global cleanup — llamado cuando una sesión se borra / se detecta como
   * inexistente. Autodissolve cualquier grupo que quede con menos de 2 chats.
   */
  const pruneChatFromGroups = useCallback(
    (chatId: string) => {
      patchGroups(current => {
        let mutated = false
        const next: SessionGroup[] = []
        for (const g of current) {
          if (!g.itemIds.includes(chatId)) {
            next.push(g)
            continue
          }
          const nextChatIds = g.itemIds.filter(id => id !== chatId)
          if (nextChatIds.length < 2) {
            mutated = true
            continue
          }
          next.push({
            ...g,
            chatIds: nextChatIds,
            activeChatId:
              g.activeChatId === chatId ? nextChatIds[0] : g.activeChatId
          })
          mutated = true
        }
        return mutated ? next : current
      })
    },
    [patchGroups]
  )

  return {
    tabGroups,
    allTabGroups,
    chatProjectById,
    createGroup,
    createPendingGroup,
    promotePendingGroup,
    dissolveGroup,
    addToGroup,
    removeFromGroup,
    renameGroup,
    setGroupColor,
    setGroupPinned,
    setGroupActiveChat,
    setGroupLayoutForMonitor,
    clearGroupLayoutForMonitor,
    reorderChatsInGroup,
    pruneChatFromGroups
  }
}

/** Convenience: find which group contains a chat id, if any. */
export function findGroupForChat(
  groups: SessionGroup[],
  chatId: string
): SessionGroup | null {
  return groups.find(g => g.itemIds.includes(chatId)) || null
}

/** Convenience: resolve a strip id (chat or group) to its display active chat. */
export function resolveStripItemActiveChat(
  stripId: string,
  groups: SessionGroup[]
): string {
  const group = groups.find(g => g.id === stripId)
  return group ? group.activeChatId : stripId
}
