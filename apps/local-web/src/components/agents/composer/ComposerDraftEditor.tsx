import type { AgentSkill, McpServer } from '@sandwalk/agent-ui-core'
import {
  type MutableRefObject,
  useMemo
} from 'react'

import {
  ComposerFileChip,
  ComposerMcpChip,
  ComposerSkillChip
} from '@/components/agents/composer/ComposerChip'
import type { ComposerAtMenuHandle } from '@/components/agents/composer/ComposerAtMenu'
import { createDraftEditorHandlers } from '@/components/agents/composer/composer-draft-editor-handlers'
import { ComposerDraftTextPart } from '@/components/agents/composer/ComposerDraftTextPart'
import type { ComposerSlashMenuHandle } from '@/components/agents/composer/ComposerSlashMenu'
import {
  type ComposerPart,
  removeComposerChipAt
} from '@/components/agents/composer-parts'
export function ComposerDraftEditor({
  draft,
  running,
  autoFocus,
  focusKey,
  composerParts,
  skills = [],
  mcpServers = [],
  textInputRefs,
  pendingCaretRef,
  autoFocusedKeyRef,
  draftRef,
  focusedPartIndex,
  setFocusedPartIndex,
  setCaretPos,
  setLocalDraft,
  commitDraft,
  onSkillChipsChange,
  onFileChipsChange,
  onOpenFile,
  onSend,
  atOpen,
  slashOpen,
  atMenuRef,
  slashMenuRef
}: {
  draft: string
  running: boolean
  autoFocus?: boolean
  focusKey?: string | null
  composerParts: ComposerPart[]
  skills?: AgentSkill[]
  mcpServers?: McpServer[]
  textInputRefs: MutableRefObject<
    Map<number, HTMLInputElement | HTMLTextAreaElement>
  >
  pendingCaretRef: MutableRefObject<number | null>
  autoFocusedKeyRef: MutableRefObject<string | null>
  draftRef: MutableRefObject<string>
  focusedPartIndex: number
  setFocusedPartIndex: (index: number) => void
  setCaretPos: (pos: number) => void
  setLocalDraft: (value: string) => void
  commitDraft: (value: string) => void
  onSkillChipsChange: (skills: string[]) => void
  onFileChipsChange?: (files: string[]) => void
  onOpenFile?: (path: string) => void
  onSend: () => void
  atOpen: boolean
  slashOpen: boolean
  atMenuRef: MutableRefObject<ComposerAtMenuHandle | null>
  slashMenuRef: MutableRefObject<ComposerSlashMenuHandle | null>
}) {
  const hasInlineChips = useMemo(
    () => composerParts.some(part => part.type !== 'text'),
    [composerParts]
  )

  const { updateTextPart, handleKeyDown } = createDraftEditorHandlers({
    draft,
    focusedPartIndex,
    atOpen,
    slashOpen,
    textInputRefs,
    atMenuRef,
    slashMenuRef,
    setFocusedPartIndex,
    setCaretPos,
    setLocalDraft,
    commitDraft,
    onSkillChipsChange,
    onFileChipsChange,
    onSend
  })

  let chipRenderIndex = -1

  return (
    <div
      className="min-h-12 max-h-32 overflow-y-auto px-2 py-1 text-[15px] leading-7"
      onClick={event => {
        if (event.target !== event.currentTarget) return
        const lastTextIndex = [...composerParts]
          .map((part, index) => (part.type === 'text' ? index : -1))
          .filter(index => index >= 0)
          .at(-1)
        if (lastTextIndex == null) return
        const node = textInputRefs.current.get(lastTextIndex)
        node?.focus()
        const len = node?.value.length ?? 0
        node?.setSelectionRange(len, len)
      }}
    >
      {composerParts.map((part, partIndex) => {
        if (part.type === 'file') {
          chipRenderIndex += 1
          const chipIndex = chipRenderIndex
          return (
            <ComposerFileChip
              key={`file-${partIndex}-${part.path}`}
              path={part.path}
              onOpenFile={onOpenFile}
              onRemove={() => {
                commitDraft(removeComposerChipAt(draft, chipIndex))
                onFileChipsChange?.([])
              }}
            />
          )
        }
        if (part.type === 'skill') {
          chipRenderIndex += 1
          const chipIndex = chipRenderIndex
          const skill = skills.find(item => item.name === part.name)
          return (
            <ComposerSkillChip
              key={`skill-${partIndex}-${part.name}`}
              name={part.name}
              iconSrc={skill?.iconSrc}
              author={skill?.author}
              source={skill?.source}
              onRemove={() => {
                commitDraft(removeComposerChipAt(draft, chipIndex))
                onSkillChipsChange([])
              }}
            />
          )
        }
        if (part.type === 'mcp') {
          chipRenderIndex += 1
          const chipIndex = chipRenderIndex
          const server = mcpServers.find(
            item => item.id === part.id || item.name === part.name
          )
          return (
            <ComposerMcpChip
              key={`mcp-${partIndex}-${part.id}`}
              id={part.id}
              name={part.name}
              catalogId={server?.catalogId}
              onRemove={() => {
                commitDraft(removeComposerChipAt(draft, chipIndex))
              }}
            />
          )
        }

        return (
          <ComposerDraftTextPart
            key={`text-${partIndex}`}
            part={part}
            partIndex={partIndex}
            composerParts={composerParts}
            hasInlineChips={hasInlineChips}
            running={running}
            autoFocus={autoFocus}
            focusKey={focusKey}
            textInputRefs={textInputRefs}
            pendingCaretRef={pendingCaretRef}
            autoFocusedKeyRef={autoFocusedKeyRef}
            draftRef={draftRef}
            setFocusedPartIndex={setFocusedPartIndex}
            setCaretPos={setCaretPos}
            updateTextPart={updateTextPart}
            handleKeyDown={handleKeyDown}
          />
        )
      })}
    </div>
  )
}
