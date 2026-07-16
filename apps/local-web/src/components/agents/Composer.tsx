import { useMemo, useRef, useState } from 'react'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import {
  ComposerAtMenu,
  type ComposerAtMenuHandle
} from '@/components/agents/composer/ComposerAtMenu'
import { ComposerAttachments } from '@/components/agents/composer/ComposerAttachments'
import { ComposerDraftEditor } from '@/components/agents/composer/ComposerDraftEditor'
import {
  ComposerSlashMenu,
  type ComposerSlashMenuHandle
} from '@/components/agents/composer/ComposerSlashMenu'
import { ComposerToolbar } from '@/components/agents/composer/ComposerToolbar'
import {
  type ComposerProps,
  type SandboxActionPhase,
  type SandboxComputeChange
} from '@/components/agents/composer/composer-props'
import { useComposerAttachments } from '@/components/agents/composer/useComposerAttachments'
import {
  useComposerDraftState,
  useComposerMentionFocus
} from '@/components/agents/composer/useComposerDraftState'
import { parseComposerParts } from '@/components/agents/composer-parts'
import { cn } from '@/lib/utils'

export type { SandboxActionPhase, SandboxComputeChange }

export function Composer({
  value,
  running,
  skills,
  mcpServers = [],
  skillChips: _skillChips,
  fileChips: _fileChips = [],
  workspaceFiles = [],
  modelOptions,
  specialists = [],
  selectedSpecialistId = null,
  sandboxStatus = null,
  sandboxPhase = 'idle',
  showAura = true,
  autoFocus = true,
  focusKey,
  onChange,
  onLiveDraftChange,
  onSkillChipsChange,
  onFileChipsChange,
  onSend,
  onStop,
  onUpload,
  onLoadSkill,
  onOpenFile,
  runtimeSettings,
  tokenUsage,
  onModelSelect,
  onReasoningSettingsChange,
  onSpecialistSelect,
  onCreateSpecialist,
  onManageSpecialists,
  onAddModels,
  onSandboxBackendSelect,
  onSandboxComputeChange,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart,
  onLoadLocalSystem,
  onPlanModeChange,
  editingQueued = false,
  onCancelEditQueued
}: ComposerProps) {
  const [auraTick, setAuraTick] = useState(0)
  const atMenuRef = useRef<ComposerAtMenuHandle | null>(null)
  const slashMenuRef = useRef<ComposerSlashMenuHandle | null>(null)

  const draftState = useComposerDraftState({
    value,
    onChange,
    onLiveDraftChange,
    autoFocus,
    focusKey,
    workspaceFiles
  })

  const {
    attachments,
    addFiles,
    removeAttachment,
    clearAttachments,
    attachmentSendPrefix,
    hasReadyAttachments,
    isUploading
  } = useComposerAttachments(onUpload, focusKey)

  useComposerMentionFocus(
    draftState.slashOpen,
    draftState.atOpen,
    draftState.focusActiveComposerInput
  )

  const selectedSpecialist =
    specialists.find(item => item.id === selectedSpecialistId) || null

  const handleSend = () => {
    const text = draftState.draftRef.current
    const prefix = attachmentSendPrefix()
    if ((!text.trim() && !prefix) || isUploading) return
    const payload = [prefix, text].filter(Boolean).join(' ').trim()
    setAuraTick(tick => tick + 1)
    draftState.clearDraftAfterSend()
    clearAttachments()
    onSend(payload)
  }

  const hasDraft = Boolean(draftState.draft.trim()) || hasReadyAttachments
  const showStopButton = running && !hasDraft
  const composerParts = useMemo(
    () => parseComposerParts(draftState.draft),
    [draftState.draft]
  )

  return (
    <div className="relative">
      {showAura ? (
        <div className="mb-3 flex justify-start pl-1">
          <AuraIconPulse
            className="text-muted-foreground/70 h-10 w-10"
            animateTick={auraTick}
          />
        </div>
      ) : null}

      <ComposerAtMenu
        ref={atMenuRef}
        open={draftState.atOpen}
        results={draftState.atResults}
        workspaceFileCount={workspaceFiles.length}
        onPick={draftState.chipInserters.insertFileChip}
        onDismiss={() => draftState.setAtDismissed(true)}
        focusInput={draftState.focusActiveComposerInput}
      />

      <ComposerSlashMenu
        ref={slashMenuRef}
        open={draftState.slashOpen}
        slash={draftState.slash}
        skills={skills}
        mcpServers={mcpServers}
        selectedSpecialist={selectedSpecialist}
        onLoadSkill={onLoadSkill}
        onPickSkill={draftState.chipInserters.insertSkillChip}
        onPickMcp={draftState.chipInserters.insertMcpChip}
        onPickExample={draftState.chipInserters.insertExample}
        onDismiss={() => draftState.setSlashDismissed(true)}
        focusInput={draftState.focusActiveComposerInput}
      />

      <div
        className={cn(
          editingQueued &&
            'overflow-hidden rounded-3xl border border-sky-500/40 bg-sky-500/5'
        )}
      >
        {editingQueued ? (
          <div className="flex items-center justify-between px-3 py-1.5 text-[12px]">
            <span className="text-sky-700 dark:text-sky-300">
              Editing queued message
            </span>
            <button
              type="button"
              onClick={() => onCancelEditQueued?.()}
              className="text-sky-700 hover:text-sky-900 dark:text-sky-300 dark:hover:text-sky-100 font-medium"
            >
              Cancel
            </button>
          </div>
        ) : null}
        <form
          onSubmit={event => {
            event.preventDefault()
            handleSend()
          }}
          onDragOver={event => {
            event.preventDefault()
            event.stopPropagation()
          }}
          onDrop={event => {
            event.preventDefault()
            event.stopPropagation()
            if (event.dataTransfer.files?.length) {
              void addFiles(event.dataTransfer.files)
            }
          }}
          onPaste={event => {
            const files = Array.from(event.clipboardData?.files || [])
            if (files.length === 0) return
            event.preventDefault()
            void addFiles(files)
          }}
          className={cn(
            'bg-card focus-within:border-muted-foreground/40 border-border rounded-3xl border p-2 shadow-[0_4px_16px_-8px_rgba(0,0,0,0.12),0_1px_2px_rgba(0,0,0,0.05)] dark:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.65)]',
            editingQueued &&
              'rounded-t-none border-x-0 border-b-0 border-t border-sky-500/25 shadow-none focus-within:border-sky-500/40'
          )}
        >
          <ComposerAttachments
            attachments={attachments}
            onRemove={removeAttachment}
          />
          <ComposerDraftEditor
            draft={draftState.draft}
            running={running}
            autoFocus={autoFocus}
            focusKey={focusKey}
            composerParts={composerParts}
            textInputRefs={draftState.textInputRefs}
            pendingCaretRef={draftState.pendingCaretRef}
            autoFocusedKeyRef={draftState.autoFocusedKeyRef}
            draftRef={draftState.draftRef}
            focusedPartIndex={draftState.focusedPartIndex}
            setFocusedPartIndex={draftState.setFocusedPartIndex}
            setCaretPos={draftState.setCaretPos}
            setLocalDraft={draftState.setLocalDraft}
            commitDraft={draftState.commitDraft}
            onSkillChipsChange={onSkillChipsChange}
            onFileChipsChange={onFileChipsChange}
            onOpenFile={onOpenFile}
            onSend={handleSend}
            atOpen={draftState.atOpen}
            slashOpen={draftState.slashOpen}
            atMenuRef={atMenuRef}
            slashMenuRef={slashMenuRef}
          />
          <ComposerToolbar
            running={running}
            showStopButton={showStopButton}
            sendDisabled={isUploading || (!hasDraft && !running)}
            modelOptions={modelOptions}
            runtimeSettings={runtimeSettings}
            specialists={specialists}
            selectedSpecialistId={selectedSpecialistId ?? null}
            sandboxStatus={sandboxStatus ?? null}
            sandboxPhase={sandboxPhase}
            tokenUsage={tokenUsage}
            onUpload={files => void addFiles(files)}
            onModelSelect={onModelSelect}
            onReasoningSettingsChange={onReasoningSettingsChange}
            onSpecialistSelect={onSpecialistSelect}
            onCreateSpecialist={onCreateSpecialist}
            onManageSpecialists={onManageSpecialists}
            onAddModels={onAddModels}
            onSandboxBackendSelect={onSandboxBackendSelect}
            onSandboxComputeChange={onSandboxComputeChange}
            onSandboxStart={onSandboxStart}
            onSandboxStop={onSandboxStop}
            onSandboxRestart={onSandboxRestart}
            onLoadLocalSystem={onLoadLocalSystem}
            onPlanModeChange={onPlanModeChange}
            onStop={onStop}
          />
        </form>
      </div>
    </div>
  )
}
