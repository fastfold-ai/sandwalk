/*
 * Persistencia del estado expandido/colapsado de un split group en el
 * sidebar. Por default los grupos se muestran CERRADOS (chevron
 * colapsado), sin importar cuándo se crearon. Solo si el usuario lo
 * abrió alguna vez guardamos la preferencia y la restauramos al remontar.
 * Cuando el usuario lo vuelve a colapsar, borramos la entrada para que
 * el default aplique otra vez si el grupo se recrea con el mismo id.
 */

const STORAGE_KEY = 'sandwalk.sidebar-group-expanded'

type ExpandedMap = Record<string, true>

function readAll(): ExpandedMap {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') return parsed as ExpandedMap
  } catch {
    // ignore
  }
  return {}
}

function writeAll(map: ExpandedMap): void {
  try {
    if (Object.keys(map).length === 0) {
      localStorage.removeItem(STORAGE_KEY)
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(map))
    }
  } catch {
    // best effort
  }
}

export function isSidebarGroupExpanded(groupId: string): boolean {
  return Boolean(readAll()[groupId])
}

export function setSidebarGroupExpanded(
  groupId: string,
  expanded: boolean
): void {
  const map = readAll()
  if (expanded) {
    map[groupId] = true
  } else {
    delete map[groupId]
  }
  writeAll(map)
}
