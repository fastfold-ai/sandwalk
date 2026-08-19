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
  if (item.kind === 'chat') {
    return attentionIds.has(item.id) ? item : null
  }
  const children = item.children.filter(chat => attentionIds.has(chat.id))
  if (children.length === 0) return null
  return { ...item, children }
}
