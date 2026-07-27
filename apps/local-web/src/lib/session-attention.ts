/** Per-session attention → macOS Dock badge when unread events pile up. */

import { setDockBadge } from '@/lib/desktop'

export const SESSION_ATTENTION_CHANGE_EVENT = 'sandwalk:session-attention-change'

const attentionIds = new Set<string>()

function syncDockBadge() {
  const count = attentionIds.size
  // Numeric labels get the standard macOS Dock badge (same as Messages).
  // Non-numeric glyphs like "•" render as a tiny off-center speck.
  void setDockBadge(count > 0 ? String(count) : null)
}

function emit() {
  syncDockBadge()
  window.dispatchEvent(new Event(SESSION_ATTENTION_CHANGE_EVENT))
}

export function markSessionAttention(sessionId: string) {
  if (!sessionId || attentionIds.has(sessionId)) return
  attentionIds.add(sessionId)
  emit()
}

export function clearSessionAttention(sessionId: string) {
  if (!sessionId || !attentionIds.has(sessionId)) return
  attentionIds.delete(sessionId)
  emit()
}

export function clearAllSessionAttention() {
  if (attentionIds.size === 0) return
  attentionIds.clear()
  emit()
}

export function hasSessionAttention(sessionId: string): boolean {
  return attentionIds.has(sessionId)
}

export function getAttentionSessionIds(): ReadonlySet<string> {
  return attentionIds
}
