import type {
  AgentSession,
  AgentSkill,
  McpServer,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import { type MutableRefObject } from 'react'
import { flushSync } from 'react-dom'

import {
  chatChipToken,
  fileChipToken,
  mcpChipToken,
  skillChipToken,
  spaceAroundChips
} from '@/components/agents/composer-parts'

export function caretAfterInsertedToken(
  nextValue: string,
  token: string
): number {
  const index = nextValue.lastIndexOf(token)
  if (index < 0) return nextValue.length
  let caret = index + token.length
  if (nextValue[caret] === ' ') caret += 1
  return caret
}

export function createChipInserters({
  draft,
  slash,
  atMention,
  hashMention,
  commitDraft,
  pendingCaretRef,
  applyComposerCaret
}: {
  draft: string
  slash: { start: number; end: number } | null
  atMention: { start: number; end: number } | null
  hashMention?: { start: number; end: number } | null
  commitDraft: (value: string) => void
  pendingCaretRef: MutableRefObject<number | null>
  applyComposerCaret: (caret: number) => boolean
}) {
  const focusAfterChipInsert = (caret: number) => {
    applyComposerCaret(caret)
    window.requestAnimationFrame(() => {
      applyComposerCaret(caret)
      window.requestAnimationFrame(() => {
        applyComposerCaret(caret)
        pendingCaretRef.current = null
      })
    })
  }

  const insertSkillChip = (skill: AgentSkill) => {
    if (!slash) return
    const before = draft.slice(0, slash.start)
    const after = draft.slice(slash.end).replace(/^\s+/u, '')
    const token = skillChipToken(skill.name)
    const nextValue = spaceAroundChips(
      after ? `${before}${token} ${after}` : `${before}${token}`
    )
    const caret = caretAfterInsertedToken(nextValue, token)
    pendingCaretRef.current = caret
    // Commit to session composer — local-only updates leave parent value '' and
    // get wiped on the next parent re-render (e.g. MCP refresh).
    flushSync(() => {
      commitDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  const insertMcpChip = (server: McpServer) => {
    if (!slash) return
    const before = draft.slice(0, slash.start)
    const after = draft.slice(slash.end).replace(/^\s+/u, '')
    const token = mcpChipToken(server.id, server.name)
    const nextValue = spaceAroundChips(
      after ? `${before}${token} ${after}` : `${before}${token}`
    )
    const caret = caretAfterInsertedToken(nextValue, token)
    pendingCaretRef.current = caret
    flushSync(() => {
      commitDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  const insertFileChip = (file: WorkspaceFile) => {
    if (!atMention) return
    const before = draft.slice(0, atMention.start)
    const after = draft.slice(atMention.end).replace(/^\s+/u, '')
    const token = fileChipToken(file.path, file.type)
    const nextValue = spaceAroundChips(
      after ? `${before}${token} ${after}` : `${before}${token}`
    )
    const caret = caretAfterInsertedToken(nextValue, token)
    pendingCaretRef.current = caret
    flushSync(() => {
      commitDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  /** Append workspace path chips (drag from Artifacts into composer). */
  const appendFileChips = (
    paths: Array<string | { path: string; type?: 'file' | 'directory' }>
  ) => {
    const tokens = paths
      .map(item => {
        if (typeof item === 'string') {
          const trimmed = item.trim()
          if (!trimmed) return null
          const kind = trimmed.endsWith('/') ? 'directory' : undefined
          return fileChipToken(trimmed, kind)
        }
        const trimmed = item.path.trim()
        if (!trimmed) return null
        return fileChipToken(trimmed, item.type)
      })
      .filter((token): token is string => Boolean(token))
    if (tokens.length === 0) return
    const joined = tokens.join(' ')
    const nextValue = spaceAroundChips(
      draft.trim() ? `${draft} ${joined}` : joined
    )
    const lastToken = tokens[tokens.length - 1]!
    const caret = caretAfterInsertedToken(nextValue, lastToken)
    pendingCaretRef.current = caret
    flushSync(() => {
      commitDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  const insertExample = (skillName: string, prompt: string) => {
    if (!slash) return
    const before = draft.slice(0, slash.start)
    const after = draft.slice(slash.end).replace(/^\s+/u, '')
    const token = skillChipToken(skillName)
    const spacedPrompt = prompt.replace(/^\s+/u, '')
    const nextValue = spaceAroundChips(
      `${before}${token} ${spacedPrompt}${after}`
    )
    const caret =
      caretAfterInsertedToken(nextValue, token) + spacedPrompt.length
    pendingCaretRef.current = caret
    flushSync(() => {
      commitDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  const insertChatChip = (session: AgentSession) => {
    if (!hashMention) return
    const before = draft.slice(0, hashMention.start)
    const after = draft.slice(hashMention.end).replace(/^\s+/u, '')
    const token = chatChipToken(session.id)
    const nextValue = spaceAroundChips(
      after ? `${before}${token} ${after}` : `${before}${token}`
    )
    const caret = caretAfterInsertedToken(nextValue, token)
    pendingCaretRef.current = caret
    flushSync(() => {
      commitDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  return {
    insertSkillChip,
    insertMcpChip,
    insertFileChip,
    insertChatChip,
    appendFileChips,
    insertExample
  }
}
