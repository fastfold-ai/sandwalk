import type { TabItem, TabItemSection } from '@/lib/sessions'

/** macOS / Codex system blue — unread dots stay distinct from tab color swatches. */
export const UNREAD_DOT_COLOR = '#5EB3FF'

const STORAGE_KEY = 'sandwalk.sidebar-unread-filter'

export function readSidebarUnreadFilter(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function writeSidebarUnreadFilter(value: boolean): void {
  try {
    if (value) localStorage.setItem(STORAGE_KEY, '1')
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // best effort
  }
}

export function filterSectionsToUnread(
  sections: TabItemSection[],
  attentionIds: ReadonlySet<string>
): TabItemSection[] {
  return sections.flatMap(section => {
    const items = section.items.flatMap(item => {
      const next = keepUnreadItem(item, attentionIds)
      return next ? [next] : []
    })
    if (items.length === 0) return []
    return [{ ...section, items }]
  })
}

function keepUnreadItem(
  item: TabItem,
  attentionIds: ReadonlySet<string>
): TabItem | null {
  // FAS-107: `TabItem` puede ser `chat`, `terminal` o `group`. Antes el
  // else-branch asumía `group` y hacía `item.children.filter(...)`, pero
  // los terminales sueltos también entran a este filtro y no tienen
  // `children` → TypeError al activar el filtro Unread del sidebar.
  if (item.kind === 'chat' || item.kind === 'terminal') {
    return attentionIds.has(item.id) ? item : null
  }
  const children = item.children.filter(child => attentionIds.has(child.id))
  if (children.length === 0) return null
  return { ...item, children }
}
