import { type Dispatch, type SetStateAction,useCallback } from 'react'

import { projectTabsKey, writeOpenTabsByProject } from '@/lib/app-storage'

export function useAppOpenTabs(
  activeProjectId: string | null,
  openTabsByProject: Record<string, string[]>,
  setOpenTabsByProject: Dispatch<SetStateAction<Record<string, string[]>>>
) {
  const tabsScopeKey = projectTabsKey(activeProjectId)
  const openTabIds = openTabsByProject[tabsScopeKey] || []

  const patchOpenTabs = useCallback(
    (scopeKey: string, updater: (current: string[]) => string[]) => {
      setOpenTabsByProject(current => {
        const prev = current[scopeKey] || []
        const next = updater(prev)
        if (
          next.length === prev.length &&
          next.every((id, index) => id === prev[index])
        ) {
          return current
        }
        const map = { ...current, [scopeKey]: next }
        writeOpenTabsByProject(map)
        return map
      })
    },
    [setOpenTabsByProject]
  )

  const setOpenTabIds = useCallback(
    (value: string[] | ((current: string[]) => string[])) => {
      patchOpenTabs(tabsScopeKey, current =>
        typeof value === 'function' ? value(current) : value
      )
    },
    [patchOpenTabs, tabsScopeKey]
  )

  const openSessionTab = useCallback(
    (id: string, scopeKey: string = tabsScopeKey) => {
      patchOpenTabs(scopeKey, current =>
        current.includes(id) ? current : [...current, id]
      )
    },
    [patchOpenTabs, tabsScopeKey]
  )

  return {
    tabsScopeKey,
    openTabIds,
    patchOpenTabs,
    setOpenTabIds,
    openSessionTab
  }
}
