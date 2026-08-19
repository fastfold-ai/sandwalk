import type {
  AgentSession,
  AgentSkill,
  McpServer,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import {
  type MutableRefObject,
  useMemo
} from 'react'

import { createDraftEditorHandlers } from '@/components/agents/composer/composer-draft-editor-handlers'
import type { ComposerAtMenuHandle } from '@/components/agents/composer/ComposerAtMenu'
import {
  ComposerFileChip,
  ComposerMcpChip,
  ComposerSkillChip,
  ComposerChatChip
} from '@/components/agents/composer/ComposerChip'
import { ComposerDraftTextPart } from '@/components/agents/composer/ComposerDraftTextPart'
import type { ComposerHashMenuHandle } from '@/components/agents/composer/ComposerHashMenu'
import type { ComposerSlashMenuHandle } from '@/components/agents/composer/ComposerSlashMenu'
import {
  type ComposerPart,
  removeComposerChipAt
} from '@/components/agents/composer-parts'
import { cn } from '@/lib/utils'

export function ComposerDraftEditor({
  draft,
  running,
  autoFocus,
  focusKey,
  composerParts,
  skills = [],
  mcpServers = [],
  workspaceFiles = [],
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
  hashOpen = false,
  atMenuRef,
  slashMenuRef,
  hashMenuRef,
  mentionChats = [],
  placeholder,
  embedded = false
}: {
  draft: string
  running: boolean
  autoFocus?: boolean
  focusKey?: string | null
  composerParts: ComposerPart[]
  skills?: AgentSkill[]
  mcpServers?: McpServer[]
  workspaceFiles?: WorkspaceFile[]
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
  hashOpen?: boolean
  atMenuRef: MutableRefObject<ComposerAtMenuHandle | null>
  slashMenuRef: MutableRefObject<ComposerSlashMenuHandle | null>
  hashMenuRef?: MutableRefObject<ComposerHashMenuHandle | null>
  mentionChats?: AgentSession[]
  placeholder?: string
  /**
   * Cuando true (split view), quita el `pt` interno del scroll y deja solo
   * `pb`. El aire con el separator de arriba lo aporta el `pt-3` externo del
   * Composer embedded — así el usuario nunca ve el texto pegado al border
   * al scrollear, porque ese aire vive fuera del área scrolleable.
   */
  embedded?: boolean
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
    hashOpen,
    textInputRefs,
    atMenuRef,
    slashMenuRef,
    hashMenuRef,
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
      className={cn(
        // El padding interno al scroll: en single-tab (`py-1.5`) el editor
        // conserva su aire arriba y abajo. En split view (`embedded`) el
        // `pt` interno pasa a 0 — el aire con el separator superior lo
        // aporta el `pt-3` del Composer, afuera del área scrolleable, así
        // no se pierde con el overflow.
        'max-h-32 overflow-y-auto px-2 text-[15px] leading-7',
        embedded ? 'pt-0 pb-1.5' : 'py-1.5',
        hasInlineChips ? 'min-h-9' : 'min-h-8'
      )}
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
          const trimmed = part.path.replace(/\/+$/u, '')
          const entry = workspaceFiles.find(
            file => file.path === part.path || file.path === trimmed
          )
          const kind =
            entry?.type === 'directory' || part.path.endsWith('/')
              ? 'directory'
              : 'file'
          return (
            <ComposerFileChip
              key={`file-${partIndex}-${part.path}`}
              path={part.path}
              kind={kind}
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
        if (part.type === 'chat') {
          chipRenderIndex += 1
          const chipIndex = chipRenderIndex
          return (
            <ComposerChatChip
              key={`chat-${partIndex}-${part.sessionId}`}
              sessionId={part.sessionId}
              title={mentionChats.find(chat => chat.id === part.sessionId)?.title}
              onRemove={() => {
                commitDraft(removeComposerChipAt(draft, chipIndex))
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
            placeholder={placeholder}
          />
        )
      })}
    </div>
  )
}
