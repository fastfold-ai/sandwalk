import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearAllSessionAttention,
  clearSessionAttention,
  getAttentionSessionIds,
  hasSessionAttention,
  markSessionAttention,
  pruneSessionAttention,
  recoverUnreadFromSessions,
  SESSION_ATTENTION_STORAGE_KEY,
  SESSION_LAST_READ_INIT_KEY,
  SESSION_LAST_READ_STORAGE_KEY} from './session-attention'

// setDockBadge is a Tauri desktop call — mock it out so the tests don't
// try to invoke a native API in jsdom.
vi.mock('@/lib/desktop', () => ({
  setDockBadge: vi.fn(() => Promise.resolve())
}))

function installMemoryLocalStorage() {
  const store = new Map<string, string>()
  const memory: Storage = {
    get length() {
      return store.size
    },
    clear() {
      store.clear()
    },
    getItem(key: string) {
      return store.has(key) ? store.get(key)! : null
    },
    key(index: number) {
      return [...store.keys()][index] ?? null
    },
    removeItem(key: string) {
      store.delete(key)
    },
    setItem(key: string, value: string) {
      store.set(key, String(value))
    }
  }
  vi.stubGlobal('localStorage', memory)
}

beforeEach(() => {
  installMemoryLocalStorage()
  clearAllSessionAttention()
  localStorage.removeItem(SESSION_ATTENTION_STORAGE_KEY)
  localStorage.removeItem(SESSION_LAST_READ_STORAGE_KEY)
  localStorage.removeItem(SESSION_LAST_READ_INIT_KEY)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('markSessionAttention / hasSessionAttention', () => {
  it('adds an id and reports it as marked', () => {
    markSessionAttention('a')
    expect(hasSessionAttention('a')).toBe(true)
  })

  it('is idempotent — marking twice keeps a single entry', () => {
    markSessionAttention('a')
    markSessionAttention('a')
    expect(getAttentionSessionIds().size).toBe(1)
  })

  it('ignores empty ids', () => {
    markSessionAttention('')
    expect(getAttentionSessionIds().size).toBe(0)
  })
})

describe('clearSessionAttention', () => {
  it('removes a marked id', () => {
    markSessionAttention('a')
    clearSessionAttention('a')
    expect(hasSessionAttention('a')).toBe(false)
  })

  it('is a no-op when the id is not marked', () => {
    clearSessionAttention('never-marked')
    expect(getAttentionSessionIds().size).toBe(0)
  })

  it('leaves other ids untouched', () => {
    markSessionAttention('a')
    markSessionAttention('b')
    clearSessionAttention('a')
    expect(hasSessionAttention('a')).toBe(false)
    expect(hasSessionAttention('b')).toBe(true)
  })
})

describe('persist and recover', () => {
  it('writes marked ids to localStorage', () => {
    markSessionAttention('slack-1')
    expect(JSON.parse(localStorage.getItem(SESSION_ATTENTION_STORAGE_KEY) || '[]')).toEqual([
      'slack-1'
    ])
  })

  it('does not mark historical chats on first recover', () => {
    const missed = recoverUnreadFromSessions(
      [{ id: 'old', lastMessageAt: '2026-01-01T00:00:00.000Z' }],
      null
    )
    expect(missed).toEqual([])
    expect(hasSessionAttention('old')).toBe(false)
  })

  it('marks chats that got a newer message after last read', () => {
    recoverUnreadFromSessions(
      [{ id: 's1', lastMessageAt: '2026-01-01T00:00:00.000Z' }],
      null
    )
    const missed = recoverUnreadFromSessions(
      [{ id: 's1', lastMessageAt: '2026-08-19T12:00:00.000Z' }],
      null
    )
    expect(missed).toEqual(['s1'])
    expect(hasSessionAttention('s1')).toBe(true)
  })

  it('skips bench, capy, the open chat, and chats without lastMessageAt', () => {
    recoverUnreadFromSessions(
      [{ id: 'seed', lastMessageAt: '2026-01-01T00:00:00.000Z' }],
      null
    )
    const missed = recoverUnreadFromSessions(
      [
        {
          id: 'bench',
          source: 'bench',
          lastMessageAt: '2026-08-19T12:00:00.000Z'
        },
        {
          id: 'capy',
          source: 'capy',
          lastMessageAt: '2026-08-19T12:00:00.000Z'
        },
        { id: 'open', lastMessageAt: '2026-08-19T12:00:00.000Z' },
        { id: 'empty' },
        { id: 'new', lastMessageAt: '2026-08-19T12:00:00.000Z' }
      ],
      'open'
    )
    expect(missed).toEqual(['new'])
    expect(hasSessionAttention('bench')).toBe(false)
    expect(hasSessionAttention('capy')).toBe(false)
    expect(hasSessionAttention('open')).toBe(false)
  })

  it('treats invalid stored last-read JSON as empty', () => {
    localStorage.setItem(SESSION_LAST_READ_INIT_KEY, '1')
    localStorage.setItem(SESSION_LAST_READ_STORAGE_KEY, '{not-json')
    const missed = recoverUnreadFromSessions(
      [{ id: 's2', lastMessageAt: '2026-08-19T12:00:00.000Z' }],
      null
    )
    expect(missed).toEqual(['s2'])
  })
})

describe('clearAllSessionAttention', () => {
  it('empties the set', () => {
    markSessionAttention('a')
    markSessionAttention('b')
    clearAllSessionAttention()
    expect(getAttentionSessionIds().size).toBe(0)
  })

  it('is a no-op when already empty', () => {
    clearAllSessionAttention()
    expect(getAttentionSessionIds().size).toBe(0)
  })
})

describe('pruneSessionAttention', () => {
  it('forgets chats that no longer exist and stray group ids, keeps terminals', () => {
    clearAllSessionAttention()
    markSessionAttention('chat-live')
    markSessionAttention('chat-deleted')
    markSessionAttention('grp_stale')
    markSessionAttention('term_other_project')
    const removed = pruneSessionAttention(['chat-live', 'chat-x'])
    expect(removed.sort()).toEqual(['chat-deleted', 'grp_stale'])
    expect([...getAttentionSessionIds()].sort()).toEqual(['chat-live', 'term_other_project'])
  })

  it('prunes terminals only when given the full terminal list', () => {
    clearAllSessionAttention()
    markSessionAttention('term_a')
    markSessionAttention('term_gone')
    expect(pruneSessionAttention([], ['term_a'])).toEqual(['term_gone'])
    expect([...getAttentionSessionIds()]).toEqual(['term_a'])
  })

  it('is a no-op when nothing is stale', () => {
    clearAllSessionAttention()
    markSessionAttention('chat-live')
    expect(pruneSessionAttention(['chat-live'])).toEqual([])
  })
})
