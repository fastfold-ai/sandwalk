/**
 * Per-session unread attention.
 * Drives the macOS Dock badge and the in-app blue unread dots on tabs/sidebar.
 */

import { setDockBadge } from '@/lib/desktop'

export const SESSION_ATTENTION_CHANGE_EVENT = 'sandwalk:session-attention-change'
export const SESSION_ATTENTION_STORAGE_KEY = 'sandwalk.session-attention'
export const SESSION_LAST_READ_STORAGE_KEY = 'sandwalk.session-last-read'
export const SESSION_LAST_READ_INIT_KEY = 'sandwalk.session-last-read-init'

const attentionIds = new Set<string>()

function readStoredIds(): string[] {
  try {
    const raw = localStorage.getItem(SESSION_ATTENTION_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter((id): id is string => typeof id === 'string' && id.length > 0)
  } catch {
    return []
  }
}

function persistAttention() {
  try {
    localStorage.setItem(
      SESSION_ATTENTION_STORAGE_KEY,
      JSON.stringify([...attentionIds])
    )
  } catch {
    // ignore quota / private mode
  }
}

function syncDockBadge() {
  const count = attentionIds.size
  // Numeric labels get the standard macOS Dock badge (same as Messages).
  // Non-numeric glyphs like "•" render as a tiny off-center speck.
  void setDockBadge(count > 0 ? String(count) : null)
}

function emit() {
  persistAttention()
  syncDockBadge()
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(SESSION_ATTENTION_CHANGE_EVENT))
  }
}

function hydrate() {
  for (const id of readStoredIds()) attentionIds.add(id)
  if (attentionIds.size > 0) syncDockBadge()
}

hydrate()

function readLastRead(): Record<string, string> {
  try {
    const raw = localStorage.getItem(SESSION_LAST_READ_STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object') return {}
    return Object.fromEntries(
      Object.entries(parsed as Record<string, unknown>).filter(
        (entry): entry is [string, string] => typeof entry[1] === 'string'
      )
    )
  } catch {
    return {}
  }
}

function writeLastRead(map: Record<string, string>) {
  try {
    localStorage.setItem(SESSION_LAST_READ_STORAGE_KEY, JSON.stringify(map))
  } catch {
    // ignore
  }
}

export function rememberSessionRead(sessionId: string, at?: string | null) {
  if (!sessionId) return
  const map = readLastRead()
  map[sessionId] = at || new Date().toISOString()
  writeLastRead(map)
}

export function markSessionAttention(sessionId: string): boolean {
  if (!sessionId || attentionIds.has(sessionId)) return false
  attentionIds.add(sessionId)
  emit()
  return true
}

export function clearSessionAttention(sessionId: string) {
  if (!sessionId) return
  rememberSessionRead(sessionId)
  if (!attentionIds.has(sessionId)) return
  attentionIds.delete(sessionId)
  emit()
}

export function clearAllSessionAttention() {
  if (attentionIds.size === 0) {
    persistAttention()
    return
  }
  attentionIds.clear()
  emit()
}

/**
 * Drop attention ids that no longer exist. The set is persisted, so a chat
 * deleted while unread (or a terminal removed from another window) otherwise
 * keeps the Bell / Dock badge lit forever. Only chat ids are pruned against
 * `knownSessionIds` — terminals (`term_*`) are pruned against
 * `knownTerminalIds` only when the caller has the complete list.
 */
export function pruneSessionAttention(
  knownSessionIds: Iterable<string>,
  knownTerminalIds?: Iterable<string> | null
): string[] {
  const sessions = new Set(knownSessionIds)
  const terminals = knownTerminalIds ? new Set(knownTerminalIds) : null
  const removed: string[] = []
  for (const id of attentionIds) {
    if (id.startsWith('grp_')) {
      removed.push(id)
      continue
    }
    if (id.startsWith('term_')) {
      if (terminals && !terminals.has(id)) removed.push(id)
      continue
    }
    if (!sessions.has(id)) removed.push(id)
  }
  if (removed.length === 0) return removed
  for (const id of removed) attentionIds.delete(id)
  emit()
  return removed
}

export function hasSessionAttention(sessionId: string): boolean {
  return attentionIds.has(sessionId)
}

export function getAttentionSessionIds(): ReadonlySet<string> {
  return attentionIds
}

export type AttentionSession = {
  id: string
  lastMessageAt?: string | null
  source?: string | null
}

/** Stamp existing chats as read once, then mark anything newer as unread. */
export function recoverUnreadFromSessions(
  sessions: AttentionSession[],
  activeSessionId: string | null
): string[] {
  const map = readLastRead()
  let initialized = false
  try {
    initialized = localStorage.getItem(SESSION_LAST_READ_INIT_KEY) === '1'
  } catch {
    initialized = false
  }
  if (!initialized) {
    for (const session of sessions) {
      if (session.source === 'bench' || session.source === 'capy') continue
      map[session.id] = session.lastMessageAt || new Date().toISOString()
    }
    writeLastRead(map)
    try {
      localStorage.setItem(SESSION_LAST_READ_INIT_KEY, '1')
    } catch {
      // ignore
    }
    return []
  }
  const newly: string[] = []
  for (const session of sessions) {
    if (session.source === 'bench' || session.source === 'capy') continue
    if (session.id === activeSessionId) continue
    const last = session.lastMessageAt
    if (!last) continue
    const readAt = map[session.id]
    if (readAt && last <= readAt) continue
    if (markSessionAttention(session.id)) newly.push(session.id)
  }
  return newly
}
