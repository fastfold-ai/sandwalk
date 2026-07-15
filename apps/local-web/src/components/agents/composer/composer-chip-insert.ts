import type {
  AgentSkill,
  McpServer,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import { type MutableRefObject } from 'react'
import { flushSync } from 'react-dom'

import {
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
  setLocalDraft,
  emittedDraftRef,
  pendingCaretRef,
  applyComposerCaret
}: {
  draft: string
  slash: { start: number; end: number } | null
  atMention: { start: number; end: number } | null
  setLocalDraft: (value: string) => void
  emittedDraftRef: MutableRefObject<string>
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
    flushSync(() => {
      emittedDraftRef.current = nextValue
      setLocalDraft(nextValue)
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
      emittedDraftRef.current = nextValue
      setLocalDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  const insertFileChip = (file: WorkspaceFile) => {
    if (!atMention) return
    const before = draft.slice(0, atMention.start)
    const after = draft.slice(atMention.end).replace(/^\s+/u, '')
    const token = fileChipToken(file.path)
    const nextValue = spaceAroundChips(
      after ? `${before}${token} ${after}` : `${before}${token}`
    )
    const caret = caretAfterInsertedToken(nextValue, token)
    pendingCaretRef.current = caret
    flushSync(() => {
      emittedDraftRef.current = nextValue
      setLocalDraft(nextValue)
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
      emittedDraftRef.current = nextValue
      setLocalDraft(nextValue)
    })
    focusAfterChipInsert(caret)
  }

  return { insertSkillChip, insertMcpChip, insertFileChip, insertExample }
}
