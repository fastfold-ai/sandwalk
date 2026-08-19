import { Upload } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import {
  type ComposerProps,
  type SandboxActionPhase,
  type SandboxComputeChange
} from '@/components/agents/composer/composer-props'
import {
  ComposerAtMenu,
  type ComposerAtMenuHandle
} from '@/components/agents/composer/ComposerAtMenu'
import { ComposerAttachments } from '@/components/agents/composer/ComposerAttachments'
import { ComposerDraftEditor } from '@/components/agents/composer/ComposerDraftEditor'
import {
  ComposerHashMenu,
  type ComposerHashMenuHandle
} from '@/components/agents/composer/ComposerHashMenu'
import {
  ComposerSlashMenu,
  type ComposerSlashMenuHandle
} from '@/components/agents/composer/ComposerSlashMenu'
import { ComposerToolbar } from '@/components/agents/composer/ComposerToolbar'
import { ComposerVoiceBar } from '@/components/agents/composer/ComposerVoiceBar'
import { useComposerAttachments } from '@/components/agents/composer/useComposerAttachments'
import {
  useComposerDraftState,
  useComposerMentionFocus
} from '@/components/agents/composer/useComposerDraftState'
import { useComposerFileDrop } from '@/components/agents/composer/useComposerFileDrop'
import { useComposerVoice } from '@/components/agents/composer/useComposerVoice'
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
  pendingAttachmentsRef,
  onResolveAttachment,
  onChange,
  onLiveDraftChange,
  onSkillChipsChange,
  onFileChipsChange,
  onSend,
  onStop,
  onUpload,
  onLoadSkill,
  onOpenFile,
  onEnsureWorkspaceFiles,
  runtimeSettings,
  tokenUsage,
  compactBusy = false,
  onCompact,
  onModelSelect,
  onReasoningSettingsChange,
  onSpecialistSelect,
  onCreateSpecialist,
  onManageSpecialists,
  onAddModels,
  onLoadModelPreferences,
  onToggleModelFavorite,
  onSandboxBackendSelect,
  onSandboxComputeChange,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart,
  onLoadLocalSystem,
  onRefreshSandbox,
  onPlanModeChange,
  editingQueued = false,
  onCancelEditQueued,
  embedded = false,
  mentionChats,
  placeholder,
  captureWindowDrops = false,
  onDropActiveChange
}: ComposerProps) {
  const [auraTick, setAuraTick] = useState(0)
  const atMenuRef = useRef<ComposerAtMenuHandle | null>(null)
  const slashMenuRef = useRef<ComposerSlashMenuHandle | null>(null)
  const hashMenuRef = useRef<ComposerHashMenuHandle | null>(null)

  const draftState = useComposerDraftState({
    value,
    onChange,
    onLiveDraftChange,
    autoFocus,
    focusKey,
    workspaceFiles,
    mentionChats,
    onEnsureWorkspaceFiles
  })

  const {
    attachments,
    addFiles,
    removeAttachment,
    clearAttachments,
    seedReadyAttachments,
    attachmentSendPrefix,
    hasReadyAttachments,
    isUploading
  } = useComposerAttachments(onUpload, focusKey)

  useEffect(() => {
    const attachmentsRef = pendingAttachmentsRef
    const pending = attachmentsRef?.current
    if (!attachmentsRef || !focusKey || !pending?.paths.length) return
    if (pending.sessionId !== focusKey) return
    let cancelled = false
    const paths = [...pending.paths]
    void (async () => {
      const seeded = await Promise.all(
        paths.map(async path => {
          const resolved = onResolveAttachment
            ? await onResolveAttachment(path)
            : null
          return {
            path,
            name: resolved?.name || path.split('/').at(-1) || path,
            contentType: resolved?.contentType || 'application/octet-stream',
            previewUrl: resolved?.previewUrl
          }
        })
      )
      if (cancelled) return
      // Clear only after a successful seed so Strict Mode remounts can retry.
      if (attachmentsRef.current === pending) {
        attachmentsRef.current = null
      }
      seedReadyAttachments(seeded)
    })()
    return () => {
      cancelled = true
    }
  }, [focusKey, onResolveAttachment, pendingAttachmentsRef, seedReadyAttachments])

  const { dragging, dropHandlers } = useComposerFileDrop({
    onFiles: files => {
      void addFiles(files)
    },
    onWorkspacePath: payload => {
      draftState.chipInserters.appendFileChips([payload])
    },
    captureWindow: captureWindowDrops,
    onDraggingChange: kind => onDropActiveChange?.(Boolean(kind))
  })

  useComposerMentionFocus(
    draftState.slashOpen,
    draftState.atOpen,
    draftState.focusActiveComposerInput,
    draftState.hashOpen
  )

  const voice = useComposerVoice({
    draft: draftState.draft,
    commitDraft: draftState.commitDraft,
    focusInput: draftState.focusActiveComposerInput
  })

  const selectedSpecialist =
    specialists.find(item => item.id === selectedSpecialistId) || null

  const handleSend = () => {
    if (voice.active || voice.busy) return
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

      <ComposerHashMenu
        ref={hashMenuRef}
        open={draftState.hashOpen}
        results={draftState.hashResults}
        chatCount={(mentionChats ?? []).filter(
          chat => chat.source !== 'capy' && chat.source !== 'bench'
        ).length}
        onPick={draftState.chipInserters.insertChatChip}
        onDismiss={() => draftState.setHashDismissed(true)}
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
        {voice.error ? (
          <div
            className="mb-2 px-1 text-[12px] text-red-600 dark:text-red-400"
            role="alert"
          >
            {voice.error}
          </div>
        ) : null}
        <form
          onSubmit={event => {
            event.preventDefault()
            handleSend()
          }}
          {...dropHandlers}
          onPaste={event => {
            const files = Array.from(event.clipboardData?.files || [])
            if (files.length === 0) return
            event.preventDefault()
            void addFiles(files)
          }}
          className={cn(
            'relative transition-colors duration-150',
            /*
             * En modo `embedded` el composer se pinta como parte inferior
             * del contenedor exterior (panel del split): sin chip propio
             * (bg/border/rounded/shadow los aporta el panel), padding
             * lateral y arriba/abajo generosos. En modo normal mantiene
             * su look de "chip flotante" clásico.
             */
            embedded
              ? 'bg-transparent border-0 rounded-none shadow-none px-4 pt-3 pb-4'
              : 'bg-card hover:border-muted-foreground/25 focus-within:border-muted-foreground/40 border-border rounded-3xl border pt-1.5 pr-2 pb-3 pl-3',
            !embedded &&
              (voice.active
                ? 'shadow-none'
                : 'shadow-[0_4px_16px_-8px_rgba(0,0,0,0.12),0_1px_2px_rgba(0,0,0,0.05)] dark:shadow-[0_8px_24px_-12px_rgba(0,0,0,0.65)]'),
            Boolean(dragging) &&
              !voice.active &&
              !embedded &&
              'border-sky-500/60 ring-2 ring-sky-500/20',
            editingQueued &&
              !voice.active &&
              !embedded &&
              'rounded-t-none border-x-0 border-b-0 border-t border-sky-500/25 shadow-none focus-within:border-sky-500/40'
          )}
        >
          {dragging && !voice.active ? (
            <div
              className="pointer-events-none absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 rounded-[inherit] bg-sky-500/10 backdrop-blur-[1px]"
              aria-hidden
            >
              <Upload className="size-6 text-sky-700 dark:text-sky-300" />
              <p className="text-sm font-medium text-sky-800 dark:text-sky-200">
                {dragging === 'reference'
                  ? 'Drop to reference'
                  : 'Drop to upload'}
              </p>
            </div>
          ) : null}
          {voice.active ? (
            <ComposerVoiceBar
              recording={voice.recording}
              transcribing={voice.transcribing}
              levels={voice.levels}
              onCancel={() => void voice.cancel()}
              onConfirm={() => void voice.toggle()}
            />
          ) : (
            <>
              <ComposerAttachments
                attachments={attachments}
                onRemove={removeAttachment}
              />
              <ComposerDraftEditor
                draft={draftState.draft}
                running={running}
                embedded={embedded}
                autoFocus={autoFocus}
                focusKey={focusKey}
                composerParts={composerParts}
                skills={skills}
                mcpServers={mcpServers}
                workspaceFiles={workspaceFiles}
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
                hashOpen={draftState.hashOpen}
                atMenuRef={atMenuRef}
                slashMenuRef={slashMenuRef}
                hashMenuRef={hashMenuRef}
                mentionChats={mentionChats}
                placeholder={placeholder}
              />
              <ComposerToolbar
                running={running}
                embedded={embedded}
                showStopButton={showStopButton}
                sendDisabled={isUploading || (!hasDraft && !running)}
                modelOptions={modelOptions}
                runtimeSettings={runtimeSettings}
                specialists={specialists}
                selectedSpecialistId={selectedSpecialistId ?? null}
                sandboxStatus={sandboxStatus ?? null}
                sandboxPhase={sandboxPhase}
                tokenUsage={tokenUsage}
                compactBusy={compactBusy}
                onCompact={onCompact}
                showMic={voice.showMic}
                voiceReady={voice.ready}
                voiceBusy={voice.busy}
                onVoiceToggle={() => void voice.toggle()}
                onUpload={files => void addFiles(files)}
                onModelSelect={onModelSelect}
                onReasoningSettingsChange={onReasoningSettingsChange}
                onSpecialistSelect={onSpecialistSelect}
                onCreateSpecialist={onCreateSpecialist}
                onManageSpecialists={onManageSpecialists}
                onAddModels={onAddModels}
                onLoadModelPreferences={onLoadModelPreferences}
                onToggleModelFavorite={onToggleModelFavorite}
                onFocusComposer={draftState.focusActiveComposerInput}
                onSandboxBackendSelect={onSandboxBackendSelect}
                onSandboxComputeChange={onSandboxComputeChange}
                onSandboxStart={onSandboxStart}
                onSandboxStop={onSandboxStop}
                onSandboxRestart={onSandboxRestart}
                onLoadLocalSystem={onLoadLocalSystem}
                onRefreshSandbox={onRefreshSandbox}
                onPlanModeChange={onPlanModeChange}
                onStop={onStop}
              />
            </>
          )}
        </form>
      </div>
    </div>
  )
}
