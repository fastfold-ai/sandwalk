import type { SessionGroup } from '@sandwalk/agent-ui-core'

export const SIDEBAR_COLLAPSED_STORAGE_KEY =
  'agent-ide-v2-assistant-ui-base-sidebar-collapsed'
export const FILES_PANEL_COLLAPSED_STORAGE_KEY =
  'agent-ide-v2-assistant-ui-base-files-panel-collapsed'
export const SHELL_PANELS_AUTO_SAVE_ID = 'fastfold.shell-panels'
export const SESSION_PANELS_AUTO_SAVE_ID = 'fastfold.session-panels'

/**
 * react-resizable-panels warns when a group's default or restored sizes
 * don't add up to 100. Drop saved layouts that fail that check so an old
 * 65/40 split doesn't print the warning on every boot.
 */
export function dropUnbalancedPanelLayouts(autoSaveId: string): void {
  if (typeof localStorage === 'undefined') return
  const key = `react-resizable-panels:${autoSaveId}`
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return
    const parsed = JSON.parse(raw) as Record<string, { layout?: unknown }>
    if (!parsed || typeof parsed !== 'object') return
    let changed = false
    for (const entryKey of Object.keys(parsed)) {
      const layout = parsed[entryKey]?.layout
      if (!Array.isArray(layout) || layout.length === 0) continue
      const total = layout.reduce<number>((sum, size) => sum + Number(size || 0), 0)
      if (Math.abs(total - 100) > 0.5) {
        delete parsed[entryKey]
        changed = true
      }
    }
    if (!changed) return
    if (Object.keys(parsed).length === 0) localStorage.removeItem(key)
    else localStorage.setItem(key, JSON.stringify(parsed))
  } catch {
    // Corrupt entry: leave it. The panel library ignores unreadable state.
  }
}
export const TERMINAL_OPEN_STORAGE_KEY = 'fastfold.terminal-open'
export const OPEN_SESSION_TABS_STORAGE_KEY = 'fastfold.open-session-tabs-by-project'
export const OPEN_SESSION_TABS_LEGACY_KEY = 'fastfold.open-session-tabs'
export const ALL_PROJECTS_TABS_KEY = '__all__'
export const PROJECT_SCOPE_STORAGE_KEY = 'fastfold.project-scope-id'
export const LAST_SESSION_BY_SCOPE_KEY = 'fastfold.last-session-by-scope'
export const RECENT_PROJECT_IDS_STORAGE_KEY = 'fastfold.recent-project-ids'
export const SIDEBAR_SECTIONS_COLLAPSED_KEY = 'fastfold.sidebar-sections-collapsed'
export const TAB_GROUPS_LEGACY_KEY = 'fastfold.tab-groups-by-project'
export const TAB_GROUPS_STORAGE_KEY = 'fastfold.tab-groups'

export function projectTabsKey(projectId: string | null | undefined) {
  return projectId || ALL_PROJECTS_TABS_KEY
}

export function readOpenTabsByProject(): Record<string, string[]> {
  try {
    const raw = localStorage.getItem(OPEN_SESSION_TABS_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as unknown
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        const result: Record<string, string[]> = {}
        for (const [key, value] of Object.entries(
          parsed as Record<string, unknown>
        )) {
          if (!Array.isArray(value)) continue
          result[key] = value.filter(
            (id): id is string => typeof id === 'string' && id.length > 0
          )
        }
        return result
      }
    }
    const legacy = localStorage.getItem(OPEN_SESSION_TABS_LEGACY_KEY)
    if (!legacy) return {}
    const parsed = JSON.parse(legacy) as unknown
    if (!Array.isArray(parsed)) return {}
    const ids = parsed.filter(
      (id): id is string => typeof id === 'string' && id.length > 0
    )
    return ids.length > 0 ? { [ALL_PROJECTS_TABS_KEY]: ids } : {}
  } catch {
    return {}
  }
}

export function writeOpenTabsByProject(map: Record<string, string[]>) {
  try {
    localStorage.setItem(OPEN_SESSION_TABS_STORAGE_KEY, JSON.stringify(map))
  } catch {
    // ignore storage failures
  }
}

export function readProjectScopeId(): string | null {
  try {
    if (typeof window !== 'undefined') {
      const projectMatch = window.location.pathname.match(
        /^\/projects\/([^/]+)/
      )
      if (projectMatch?.[1]) return decodeURIComponent(projectMatch[1])
    }
    const raw = localStorage.getItem(PROJECT_SCOPE_STORAGE_KEY)
    if (!raw || raw === ALL_PROJECTS_TABS_KEY) return null
    return raw
  } catch {
    return null
  }
}

export function writeProjectScopeId(projectId: string | null) {
  try {
    localStorage.setItem(
      PROJECT_SCOPE_STORAGE_KEY,
      projectId || ALL_PROJECTS_TABS_KEY
    )
  } catch {
    // ignore storage failures
  }
}

export function readLastSessionByScope(): Record<string, string> {
  try {
    const raw = localStorage.getItem(LAST_SESSION_BY_SCOPE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return {}
    }
    const result: Record<string, string> = {}
    for (const [key, value] of Object.entries(
      parsed as Record<string, unknown>
    )) {
      if (typeof value === 'string' && value.length > 0) result[key] = value
    }
    return result
  } catch {
    return {}
  }
}

export function writeLastSessionByScope(map: Record<string, string>) {
  try {
    localStorage.setItem(LAST_SESSION_BY_SCOPE_KEY, JSON.stringify(map))
  } catch {
    // ignore storage failures
  }
}

export function readRecentProjectIds(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_PROJECT_IDS_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (id): id is string => typeof id === 'string' && id.length > 0
    )
  } catch {
    return []
  }
}

export function writeRecentProjectIds(ids: string[]) {
  try {
    localStorage.setItem(RECENT_PROJECT_IDS_STORAGE_KEY, JSON.stringify(ids))
  } catch {
    // ignore storage failures
  }
}

export function readCollapsedSidebarSections(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(SIDEBAR_SECTIONS_COLLAPSED_KEY)
    if (!raw) return { archive: true }
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return { archive: true }
    }
    const next: Record<string, boolean> = { archive: true }
    for (const [key, value] of Object.entries(
      parsed as Record<string, unknown>
    )) {
      if (typeof value === 'boolean') next[key] = value
    }
    return next
  } catch {
    return { archive: true }
  }
}

export function writeCollapsedSidebarSections(value: Record<string, boolean>) {
  try {
    localStorage.setItem(SIDEBAR_SECTIONS_COLLAPSED_KEY, JSON.stringify(value))
  } catch {
    // ignore storage failures
  }
}

/**
 * Read the persisted tab groups. Groups are strictly a UI preference (how
 * the user arranges tabs into split views), not chat data — los chats
 * viven en el server. A partir de la migración multi-proyecto, los grupos
 * viven en una lista plana única en vez de por scope de proyecto: el
 * grupo se muestra en cada proyecto donde tenga al menos un chat.
 *
 * Compatibilidad: si existe la key vieja `tab-groups-by-project`, se
 * aplana (unimos todos los grupos deduplicados por id) y se retorna. La
 * migración efectiva a la nueva key ocurre al primer `writeTabGroups`.
 */
export function readTabGroups(): SessionGroup[] {
  try {
    const raw = localStorage.getItem(TAB_GROUPS_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as unknown
      if (Array.isArray(parsed)) {
        return parsed
          .filter(
            (item): item is SessionGroup & { chatIds?: string[] } =>
              !!item &&
              typeof item === 'object' &&
              typeof (item as SessionGroup).id === 'string' &&
              // Aceptar `itemIds` (nuevo, X5.2) o `chatIds` (legacy).
              (Array.isArray((item as SessionGroup).itemIds) ||
                Array.isArray(
                  (item as { chatIds?: unknown }).chatIds
                ))
          )
          // FAS-107 X5.2 · migración: promover `chatIds` legacy a `itemIds`
          // al leer del localStorage. Datos guardados antes del rename
          // siguen funcionando.
          .map(g => {
            if (Array.isArray(g.itemIds)) return g
            const legacy = (g as unknown as { chatIds: string[] }).chatIds
            return { ...g, itemIds: legacy }
          })
          // Los pending groups son estado UI efímero (mientras el usuario
          // arma el split desde el picker). No los persistimos entre
          // sesiones — al recargar se descartan y el chat de origen
          // vuelve suelto naturalmente.
          .filter(g => !g.isPending)
          // Legacy shape: el layout persistido usaba `ChatCell[]` (grid
          // absoluto de x/y/w/h). El nuevo shape es un árbol PaneNode.
          // Descartamos los layouts viejos silenciosamente para que la
          // migración sea invisible — el grupo cae al tree default.
          .map(g => (g.layout ? { ...g, layout: sanitizeLayout(g.layout) } : g))
      }
    }
    // Fallback: migrar desde el schema por-proyecto (aplanado + dedupe).
    const legacy = localStorage.getItem(TAB_GROUPS_LEGACY_KEY)
    if (!legacy) return []
    const parsed = JSON.parse(legacy) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      return []
    }
    const seen = new Set<string>()
    const flat: SessionGroup[] = []
    for (const value of Object.values(parsed as Record<string, unknown>)) {
      if (!Array.isArray(value)) continue
      for (const item of value) {
        if (
          !item ||
          typeof item !== 'object' ||
          typeof (item as SessionGroup).id !== 'string'
        ) {
          continue
        }
        const withItemIds = item as SessionGroup
        const withLegacy = item as { chatIds?: unknown }
        // X5.2: aceptar `itemIds` (nuevo) o `chatIds` (legacy).
        const hasItemIds = Array.isArray(withItemIds.itemIds)
        const hasChatIds = Array.isArray(withLegacy.chatIds)
        if (!hasItemIds && !hasChatIds) continue
        const g: SessionGroup = hasItemIds
          ? withItemIds
          : {
              ...(item as SessionGroup),
              itemIds: withLegacy.chatIds as string[]
            }
        if (seen.has(g.id)) continue
        seen.add(g.id)
        flat.push(g)
      }
    }
    return flat
  } catch {
    return []
  }
}

/**
 * Filter a persisted `layout` object, keeping only per-monitor entries
 * whose value already looks like a `PaneNode`. Legacy `ChatCell[]` shapes
 * (arrays instead of tree nodes) are dropped — the group falls back to
 * the default tiling tree on read.
 */
function sanitizeLayout(
  layout: NonNullable<SessionGroup['layout']>
): NonNullable<SessionGroup['layout']> | undefined {
  const perMonitor: Record<string, NonNullable<SessionGroup['layout']>['perMonitor'][string]> = {}
  for (const [fp, value] of Object.entries(layout.perMonitor || {})) {
    if (looksLikePaneNode(value)) perMonitor[fp] = value
  }
  return Object.keys(perMonitor).length > 0 ? { perMonitor } : undefined
}

/**
 * Recursive shape check for a persisted `PaneNode`. Rejects any tree
 * that isn't fully well-formed — this includes a chat leaf without a
 * chatId, a branch with mismatched `ratios` and `children` lengths,
 * ratios that don't sum to ~1, an unknown `direction`, or a child that
 * itself fails the same check. Rejected trees are dropped by
 * `sanitizeLayout` and the group falls back to the default row.
 */
function looksLikePaneNode(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false
  const v = value as {
    type?: string
    chatId?: string
    terminalId?: string
    ref?: { id?: unknown; kind?: unknown }
    direction?: string
    ratios?: unknown
    children?: unknown[]
  }
  if (v.type === 'chat') {
    if (typeof v.chatId !== 'string' || v.chatId.length === 0) return false
    // Reject the transient picker placeholder id used by
    // `ChatTilingContainer` — it's UI state, never a real chat.
    // Duplicated string on purpose to avoid a UI → storage import.
    if (v.chatId === '__picker__') return false
    return true
  }
  // FAS-107: el árbol acepta hojas `terminal` y `ref` desde que se agregó
  // soporte para terminales en el split. Sin este check el validador
  // rechazaba cualquier árbol con un terminal y `sanitizeLayout`
  // devolvía `undefined`, tirando toda la topología persistida.
  if (v.type === 'terminal') {
    return typeof v.terminalId === 'string' && v.terminalId.length > 0
  }
  if (v.type === 'ref') {
    return (
      !!v.ref &&
      typeof v.ref.id === 'string' &&
      (v.ref.kind === 'chat' || v.ref.kind === 'terminal')
    )
  }
  if (v.type !== 'branch') return false
  if (v.direction !== 'horizontal' && v.direction !== 'vertical') return false
  if (!Array.isArray(v.children) || v.children.length === 0) return false
  if (!Array.isArray(v.ratios)) return false
  if (v.ratios.length !== v.children.length) return false
  const sum = (v.ratios as unknown[]).reduce<number>((acc, r) => {
    if (typeof r !== 'number' || Number.isNaN(r) || r < 0) return NaN
    return acc + r
  }, 0)
  if (!Number.isFinite(sum) || Math.abs(sum - 1) > 0.01) return false
  return v.children.every(child => looksLikePaneNode(child))
}

export function writeTabGroups(groups: SessionGroup[]) {
  try {
    // FAS-107 Fase 4: los pending groups son estado UI efímero (mientras
    // el picker está abierto). Nunca los persistimos — si el user cierra
    // la app antes de confirmar el partner, el pending muere y el chat
    // de origen vuelve a ser tab suelto natural. Complementa el filtro
    // defensivo en `readTabGroups`.
    const persistable = groups.filter(g => !g.isPending)
    localStorage.setItem(TAB_GROUPS_STORAGE_KEY, JSON.stringify(persistable))
  } catch {
    // ignore storage failures
  }
}
