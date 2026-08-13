import type { SessionGroup } from '@sandwalk/agent-ui-core'
import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useMemo
} from 'react'

import {
  projectTabsKey,
  writeTabGroupsByProject
} from '@/lib/app-storage'

/**
 * Store hook that mirrors `useAppOpenTabs` but for split-view groups.
 *
 * A group's lifecycle in relation to `openTabIds`:
 *   - createGroup([A, B, C]) removes A/B/C from openTabIds and inserts `grp_x`
 *     at the position of the first affected id.
 *   - dissolveGroup(grp_x) removes `grp_x` from openTabIds and re-inserts the
 *     group's chatIds at the same position.
 *   - addToGroup(grp_x, D) removes D from openTabIds (D now lives inside the
 *     group). If D was inside another group, it's removed there too.
 *   - removeFromGroup(grp_x, chatId) puts chatId back into openTabIds RIGHT
 *     AFTER the group's position, keeping the visual order intuitive. If the
 *     group is left with a single chat, the caller should dissolveGroup after
 *     confirming with the user.
 *
 * `openTabIds` therefore always contains a MIX of chat ids and group ids —
 * `isSessionGroupId(id)` disambiguates.
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
 * mirando *todos* los grupos existentes (todos los scopes). Se recicla:
 * si tenías Group 1, 2, 3 y borrás el 2, el próximo grupo se llama
 * "Group 2" — es el hueco más chico disponible. Al renombrar el
 * usuario, el nombre custom reemplaza este auto.
 */
function nextAutoGroupName(
  existingGroups: SessionGroup[]
): string {
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

export function useAppTabGroups(
  activeProjectId: string | null,
  tabGroupsByProject: Record<string, SessionGroup[]>,
  setTabGroupsByProject: Dispatch<
    SetStateAction<Record<string, SessionGroup[]>>
  >,
  setOpenTabIds: SetOpenTabIds
) {
  const scopeKey = projectTabsKey(activeProjectId)
  const tabGroups = tabGroupsByProject[scopeKey] || []

  const patchGroups = useCallback(
    (
      key: string,
      updater: (current: SessionGroup[]) => SessionGroup[]
    ) => {
      setTabGroupsByProject(current => {
        const prev = current[key] || []
        const next = updater(prev)
        if (next === prev) return current
        const map = { ...current, [key]: next }
        writeTabGroupsByProject(map)
        return map
      })
    },
    [setTabGroupsByProject]
  )

  const createGroup = useCallback(
    (chatIds: string[], overrides?: Partial<SessionGroup>): string | null => {
      if (chatIds.length < 2) return null
      const id = overrides?.id ?? generateGroupId()
      const allExisting: SessionGroup[] = []
      for (const key of Object.keys(tabGroupsByProject)) {
        for (const g of tabGroupsByProject[key] || []) allExisting.push(g)
      }
      const name =
        overrides?.name && overrides.name.trim().length > 0
          ? overrides.name
          : nextAutoGroupName(allExisting)
      const group: SessionGroup = {
        id,
        name,
        color: overrides?.color ?? null,
        pinned: overrides?.pinned ?? false,
        chatIds,
        activeChatId: overrides?.activeChatId ?? chatIds[0]
      }
      patchGroups(scopeKey, current => [...current, group])
      setOpenTabIds(current => {
        const firstIdx = current.findIndex(tabId => chatIds.includes(tabId))
        const filtered = current.filter(tabId => !chatIds.includes(tabId))
        const insertAt = firstIdx >= 0 ? firstIdx : 0
        filtered.splice(insertAt, 0, id)
        return filtered
      })
      return id
    },
    [patchGroups, scopeKey, setOpenTabIds, tabGroupsByProject]
  )

  const dissolveGroup = useCallback(
    (groupId: string) => {
      const group = tabGroups.find(g => g.id === groupId)
      if (!group) return
      patchGroups(scopeKey, current =>
        current.filter(g => g.id !== groupId)
      )
      setOpenTabIds(current => {
        const idx = current.indexOf(groupId)
        if (idx < 0) return [...current, ...group.chatIds]
        return [
          ...current.slice(0, idx),
          ...group.chatIds,
          ...current.slice(idx + 1)
        ]
      })
    },
    [patchGroups, scopeKey, setOpenTabIds, tabGroups]
  )

  /** Add a chat to an existing group. If the chat is inside another group,
   * it's removed from there first (a chat can only live in one group). */
  const addToGroup = useCallback(
    (groupId: string, chatId: string) => {
      patchGroups(scopeKey, current => {
        // Remove chatId from any other group.
        const scrubbed = current.map(g =>
          g.id === groupId
            ? g
            : g.chatIds.includes(chatId)
              ? { ...g, chatIds: g.chatIds.filter(c => c !== chatId) }
              : g
        )
        // Add chatId to target group (skip if already there).
        return scrubbed.map(g =>
          g.id === groupId && !g.chatIds.includes(chatId)
            ? { ...g, chatIds: [...g.chatIds, chatId] }
            : g
        )
      })
      setOpenTabIds(current => current.filter(id => id !== chatId))
    },
    [patchGroups, scopeKey, setOpenTabIds]
  )

  /** Take a chat out of its group. Returns the new group size so the caller
   * can decide whether to prompt for dissolve when it drops to 1. */
  const removeFromGroup = useCallback(
    (groupId: string, chatId: string): number => {
      const group = tabGroups.find(g => g.id === groupId)
      if (!group || !group.chatIds.includes(chatId)) return -1
      const nextIds = group.chatIds.filter(id => id !== chatId)
      const nextActive =
        group.activeChatId === chatId
          ? nextIds[0] ?? group.activeChatId
          : group.activeChatId
      patchGroups(scopeKey, current =>
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
    [patchGroups, scopeKey, setOpenTabIds, tabGroups]
  )

  const renameGroup = useCallback(
    (groupId: string, name: string) => {
      patchGroups(scopeKey, current =>
        current.map(g => (g.id === groupId ? { ...g, name } : g))
      )
    },
    [patchGroups, scopeKey]
  )

  const setGroupColor = useCallback(
    (groupId: string, color: string | null) => {
      patchGroups(scopeKey, current =>
        current.map(g => (g.id === groupId ? { ...g, color } : g))
      )
    },
    [patchGroups, scopeKey]
  )

  const setGroupPinned = useCallback(
    (groupId: string, pinned: boolean) => {
      patchGroups(scopeKey, current =>
        current.map(g => (g.id === groupId ? { ...g, pinned } : g))
      )
    },
    [patchGroups, scopeKey]
  )

  const setGroupActiveChat = useCallback(
    (groupId: string, chatId: string) => {
      patchGroups(scopeKey, current =>
        current.map(g =>
          g.id === groupId && g.chatIds.includes(chatId)
            ? { ...g, activeChatId: chatId }
            : g
        )
      )
    },
    [patchGroups, scopeKey]
  )

  /** Reorder the chats inside a group (drag-reorder in split view or the
   * dropdown / sidebar branches). */
  const reorderChatsInGroup = useCallback(
    (groupId: string, orderedChatIds: string[]) => {
      patchGroups(scopeKey, current =>
        current.map(g => {
          if (g.id !== groupId) return g
          // Only accept a permutation of the current chatIds.
          const currentSet = new Set(g.chatIds)
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
    [patchGroups, scopeKey]
  )

  /**
   * Global cleanup — called when a chat session is deleted / detected as gone.
   * Runs across ALL project scopes because a chat can appear anywhere.
   * Auto-dissolves any group that drops below 2 chats.
   */
  const pruneChatFromGroups = useCallback(
    (chatId: string) => {
      setTabGroupsByProject(current => {
        let mutated = false
        const nextMap: Record<string, SessionGroup[]> = {}
        for (const [key, groups] of Object.entries(current)) {
          const nextGroups: SessionGroup[] = []
          for (const g of groups) {
            if (!g.chatIds.includes(chatId)) {
              nextGroups.push(g)
              continue
            }
            const nextChatIds = g.chatIds.filter(id => id !== chatId)
            if (nextChatIds.length < 2) {
              // Auto-dissolve: caller should also insert the remaining chatId
              // back into openTabIds if it wants the tab to stay visible.
              mutated = true
              continue
            }
            nextGroups.push({
              ...g,
              chatIds: nextChatIds,
              activeChatId:
                g.activeChatId === chatId
                  ? nextChatIds[0]
                  : g.activeChatId
            })
            mutated = true
          }
          nextMap[key] = nextGroups
        }
        if (!mutated) return current
        writeTabGroupsByProject(nextMap)
        return nextMap
      })
    },
    [setTabGroupsByProject]
  )

  /*
   * Grupos de TODOS los scopes (unificados). Sirve para consultas globales
   * (por ejemplo `chatIsInsideAnyGroup` en App.tsx, o resolver un `grp_xxx`
   * cuando el proyecto activo no coincide con el scope donde se creó).
   * Las mutaciones siguen sobre el scope activo (`tabGroups`).
   */
  const allTabGroups = useMemo(() => {
    const out: SessionGroup[] = []
    for (const key of Object.keys(tabGroupsByProject)) {
      for (const g of tabGroupsByProject[key] || []) out.push(g)
    }
    return out
  }, [tabGroupsByProject])

  return {
    scopeKey,
    tabGroups,
    allTabGroups,
    createGroup,
    dissolveGroup,
    addToGroup,
    removeFromGroup,
    renameGroup,
    setGroupColor,
    setGroupPinned,
    setGroupActiveChat,
    reorderChatsInGroup,
    pruneChatFromGroups
  }
}

/** Convenience: find which group contains a chat id, if any. */
export function findGroupForChat(
  groups: SessionGroup[],
  chatId: string
): SessionGroup | null {
  return groups.find(g => g.chatIds.includes(chatId)) || null
}

/** Convenience: resolve a strip id (chat or group) to its display active chat. */
export function resolveStripItemActiveChat(
  stripId: string,
  groups: SessionGroup[]
): string {
  const group = groups.find(g => g.id === stripId)
  return group ? group.activeChatId : stripId
}
