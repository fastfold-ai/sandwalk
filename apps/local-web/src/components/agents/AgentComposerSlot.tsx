import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentMessage,
  AgentSession,
  AgentSkill,
  AgentSkillDetail,
  McpServer,
  RuntimeSettings,
  SessionSandboxStatus,
  Specialist,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import type { Dispatch, MutableRefObject, SetStateAction } from 'react'
import { useEffect, useMemo, useState } from 'react'
import type { NavigateFunction } from 'react-router-dom'
import { toast } from 'sonner'

import {
  Composer,
  type SandboxActionPhase
} from '@/components/agents/Composer'
import { type SandboxComputeChange } from '@/components/agents/composer/sandbox-utils'
import {
  PLAN_MODE_EVENT,
  requestPlanMode,
  takeQueuedPlanMode
} from '@/components/agents/empty-start'
import { QueuedMessages } from '@/components/agents/QueuedMessages'
import {
  contentTypeFromPath,
  needsAttachmentPreview
} from '@/lib/attachment-mime'
import {
  type ComposerModelOption,
  resolveComposerModelOption
} from '@/lib/composer-models'
import { isDraftAgentSessionId } from '@/lib/draft-agent'
import { mediaObjectUrlFromFile } from '@/lib/media-src'
import {
  modelSupportsMultimodalKind,
  multimodalKindForFile,
  unsupportedMultimodalHint
} from '@/lib/multimodal-attach'
import type { QueuedMessage } from '@/lib/sessions'

type AgentComposerSlotProps = {
  sessionId: string | null
  session: AgentSession | null
  client: LocalAgentClient
  navigate: NavigateFunction
  pendingAttachmentsRef: MutableRefObject<{
    sessionId: string
    paths: string[]
  } | null>
  ensureAgentSession: (
    projectId?: string | null,
    options?: { navigate?: boolean }
  ) => Promise<string | null>
  composerLiveRef: MutableRefObject<string>
  queuedMessages: QueuedMessage[]
  editingQueuedId: string | null
  editQueuedMessage: (id: string) => void
  sendQueuedMessageNow: (id: string) => void
  removeQueuedMessage: (id: string) => void
  cancelEditQueuedMessage: () => void
  composer: string
  runActive: boolean
  skills: AgentSkill[]
  mcpServers: McpServer[]
  composerSkills: string[]
  composerFiles: string[]
  workspaceFiles: WorkspaceFile[]
  modelOptions: ComposerModelOption[]
  specialists: Specialist[]
  sessionSandboxStatus: SessionSandboxStatus | null
  sessionSandboxPhase: SandboxActionPhase
  setComposer: (value: string | ((current: string) => string)) => void
  setComposerSkills: (value: string[] | ((current: string[]) => string[])) => void
  setComposerFiles: (value: string[] | ((current: string[]) => string[])) => void
  setFilesPanelCollapsed: Dispatch<SetStateAction<boolean>>
  setPendingOpenPath: Dispatch<SetStateAction<string | null>>
  handleComposerSend: (text: string) => void
  handleStop: () => void | Promise<void>
  loadSkillDetail: (name: string) => Promise<AgentSkillDetail>
  setWorkspaceVersion: Dispatch<SetStateAction<number>>
  onEnsureWorkspaceFiles?: () => void | Promise<void>
  runtimeSettings: RuntimeSettings | null
  tokenUsage: { inputTokens: number; outputTokens: number }
  onMessagesReloaded?: (messages: AgentMessage[]) => void
  selectSessionSpecialist: (specialistId: string | null) => Promise<void>
  selectSessionSandboxBackend: (
    backend: 'builtin' | 'modal'
  ) => void | Promise<void>
  updateSessionSandboxCompute: (
    changes: SandboxComputeChange
  ) => Promise<void>
  startSessionSandbox: () => Promise<void>
  stopSessionSandbox: () => Promise<void>
  restartSessionSandbox: () => Promise<void>
  refreshSessionSandbox: (
    targetSessionId?: string | null
  ) => Promise<SessionSandboxStatus | null>
  setRuntimeSettings: Dispatch<SetStateAction<RuntimeSettings | null>>
  onSessionUpdated?: (session: AgentSession) => void
  loadModelOptions: () => Promise<void>
  /** Reenvía al `Composer` para que se pinte sin chip propio. */
  embedded?: boolean
  /**
   * En split view, N paneles montan y cada uno tiene su propio slot. Si
   * todos autofocean, el último "gana" y su focus bubblea por
   * `onFocusCapture` del ChatTilingContainer, que llama `onFocusChat` con
   * ese chatId — pisando el chat que el usuario acababa de elegir desde
   * el sidebar. En single-tab siempre queremos autofocus; en split solo
   * el panel focused.
   */
  autoFocus?: boolean
}

export function AgentComposerSlot({
  sessionId,
  session,
  client,
  navigate,
  pendingAttachmentsRef,
  ensureAgentSession,
  composerLiveRef,
  queuedMessages,
  editingQueuedId,
  editQueuedMessage,
  sendQueuedMessageNow,
  removeQueuedMessage,
  cancelEditQueuedMessage,
  composer,
  runActive,
  skills,
  mcpServers,
  composerSkills,
  composerFiles,
  workspaceFiles,
  modelOptions,
  specialists,
  sessionSandboxStatus,
  sessionSandboxPhase,
  setComposer,
  setComposerSkills,
  setComposerFiles,
  setFilesPanelCollapsed,
  setPendingOpenPath,
  handleComposerSend,
  handleStop,
  loadSkillDetail,
  setWorkspaceVersion,
  onEnsureWorkspaceFiles,
  runtimeSettings,
  tokenUsage,
  onMessagesReloaded,
  selectSessionSpecialist,
  selectSessionSandboxBackend,
  updateSessionSandboxCompute,
  startSessionSandbox,
  stopSessionSandbox,
  restartSessionSandbox,
  refreshSessionSandbox,
  setRuntimeSettings,
  onSessionUpdated,
  loadModelOptions,
  embedded,
  autoFocus = true
}: AgentComposerSlotProps) {
  const [compactBusy, setCompactBusy] = useState(false)
  // Existing chats keep their own model; draft/new chats use global defaults.
  const isDraftSession =
    !sessionId || isDraftAgentSessionId(sessionId) || !session
  const composerRuntimeSettings = useMemo(() => {
    if (!runtimeSettings) return null
    if (isDraftSession || !session?.model) return runtimeSettings
    return {
      ...runtimeSettings,
      provider: session.provider || runtimeSettings.provider,
      model: session.model,
      openaiProfileId:
        session.openaiProfileId ?? runtimeSettings.openaiProfileId ?? null
    }
  }, [isDraftSession, runtimeSettings, session])

  useEffect(() => {
    const apply = (enabled: boolean) => {
      void client
        .updateRuntimeSettings({ planMode: enabled })
        .then(setRuntimeSettings)
        .catch(err => console.error('plan mode failed', err))
    }
    const queued = takeQueuedPlanMode()
    if (queued !== null) apply(queued)
    const onPlan = () => {
      const next = takeQueuedPlanMode()
      if (next !== null) apply(next)
    }
    window.addEventListener(PLAN_MODE_EVENT, onPlan)
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !event.shiftKey) return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target
      if (!(target instanceof Element) || !target.closest('form')) return
      event.preventDefault()
      requestPlanMode(!runtimeSettings?.planMode)
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener(PLAN_MODE_EVENT, onPlan)
      window.removeEventListener('keydown', onKey)
    }
  }, [client, runtimeSettings?.planMode, setRuntimeSettings])

  return (
    <>
      <QueuedMessages
        messages={queuedMessages}
        editingId={editingQueuedId}
        onEdit={editQueuedMessage}
        onSendNow={sendQueuedMessageNow}
        onRemove={removeQueuedMessage}
      />
      <Composer
        // Stable across draft → real session so first send does not remount.
        key="session-composer"
        value={composer}
        running={runActive}
        embedded={embedded}
        skills={skills}
        mcpServers={mcpServers}
        skillChips={composerSkills}
        fileChips={composerFiles}
        workspaceFiles={workspaceFiles}
        modelOptions={modelOptions}
        specialists={specialists}
        selectedSpecialistId={session?.specialistId ?? null}
        sandboxStatus={sessionSandboxStatus}
        sandboxPhase={sessionSandboxPhase}
        showAura={false}
        autoFocus={autoFocus}
        focusKey={
          sessionId && !isDraftAgentSessionId(sessionId)
            ? sessionId
            : 'draft'
        }
        pendingAttachmentsRef={pendingAttachmentsRef}
        onResolveAttachment={async path => {
          const id =
            sessionId && !isDraftAgentSessionId(sessionId)
              ? sessionId
              : await ensureAgentSession(undefined, { navigate: false })
          if (!id || isDraftAgentSessionId(id)) return null
          const name = path.split('/').at(-1) || path
          const contentType = contentTypeFromPath(path)
          if (!needsAttachmentPreview(contentType, path)) {
            return { name, contentType }
          }
          try {
            const file = await client.readFile(id, path)
            return {
              name,
              contentType: file.mimeType || contentType,
              previewUrl: mediaObjectUrlFromFile({
                encoding: file.encoding,
                content: file.content,
                mimeType: file.mimeType || contentType,
                name
              })
            }
          } catch {
            return { name, contentType }
          }
        }}
        editingQueued={Boolean(editingQueuedId)}
        onCancelEditQueued={cancelEditQueuedMessage}
        onChange={setComposer}
        onLiveDraftChange={text => {
          composerLiveRef.current = text
        }}
        onSkillChipsChange={setComposerSkills}
        onFileChipsChange={setComposerFiles}
        onOpenFile={path => {
          setFilesPanelCollapsed(false)
          setPendingOpenPath(path)
        }}
        onEnsureWorkspaceFiles={onEnsureWorkspaceFiles}
        onSend={handleComposerSend}
        onStop={() => void handleStop()}
        onLoadSkill={loadSkillDetail}
        onUpload={async files => {
          // Stay on /agents/new after materializing so the composer does not
          // remount (no skeleton / thumbnail flicker). Route swaps on send.
          // Any format / size is accepted (local workspace).
          const id = await ensureAgentSession(undefined, { navigate: false })
          if (!id || isDraftAgentSessionId(id)) {
            toast.error('Could not create session for upload')
            return []
          }
          const activeModel = resolveComposerModelOption(modelOptions, {
            provider: runtimeSettings?.provider || '',
            model: runtimeSettings?.model || '',
            openaiProfileId: runtimeSettings?.openaiProfileId ?? null
          })
          for (const file of files) {
            const kind = multimodalKindForFile(file)
            if (
              kind &&
              !modelSupportsMultimodalKind(activeModel, kind)
            ) {
              toast.message(unsupportedMultimodalHint(kind))
            }
          }
          const uploaded = await Promise.all(
            files.map(file => client.uploadFile(id, file))
          )
          setWorkspaceVersion(current => current + 1)
          return uploaded.map(item => ({
            path: item.path,
            name: item.path.split('/').at(-1) || item.path,
            mimeType: item.mimeType
          }))
        }}
        runtimeSettings={composerRuntimeSettings}
        tokenUsage={tokenUsage}
        compactBusy={compactBusy}
        onCompact={
          sessionId && !isDraftAgentSessionId(sessionId)
            ? async () => {
                if (compactBusy || runActive) return
                setCompactBusy(true)
                try {
                  const result = await client.compactSession(sessionId)
                  const history = await client.listMessages(sessionId)
                  onMessagesReloaded?.(history)
                  toast.success(
                    `Compacted ${result.turnsBefore} turns → ${result.turnsAfter}`
                  )
                } catch (cause) {
                  toast.error(
                    cause instanceof Error
                      ? cause.message
                      : 'Compact failed'
                  )
                } finally {
                  setCompactBusy(false)
                }
              }
            : undefined
        }
        onSpecialistSelect={selectSessionSpecialist}
        onCreateSpecialist={() => navigate('/dashboard/specialists/new')}
        onManageSpecialists={() => navigate('/dashboard/specialists')}
        onAddModels={() => navigate('/dashboard/models')}
        onLoadModelPreferences={() => client.getModelPreferences()}
        onToggleModelFavorite={option =>
          client.toggleModelFavorite({
            provider: option.provider,
            model: option.model,
            profileId: option.profileId
          })
        }
        onSandboxBackendSelect={selectSessionSandboxBackend}
        onSandboxComputeChange={changes =>
          void updateSessionSandboxCompute(changes)
        }
        onSandboxStart={() => void startSessionSandbox()}
        onSandboxStop={() => void stopSessionSandbox()}
        onSandboxRestart={() => void restartSessionSandbox()}
        onRefreshSandbox={() => void refreshSessionSandbox()}
        onLoadLocalSystem={async () => {
          const report = await client.getServerStatus()
          return report.system
        }}
        onModelSelect={async (provider, model, profileId) => {
          if (profileId) {
            try {
              await client.updateModelProfile(profileId, {
                setActive: true
              })
            } catch {
              // Profile activation is best-effort for local models.
            }
          }
          // Local profile models are labeled provider=local in the
          // catalog, but the runtime still speaks OpenAI-compatible.
          const runtimeProvider =
            provider === 'local' || profileId ? 'openai' : provider
          if (isDraftSession || !sessionId) {
            setRuntimeSettings(
              await client.updateRuntimeSettings({
                provider: runtimeProvider,
                model
              })
            )
            return
          }
          const updated = await client.updateSession(sessionId, {
            provider: runtimeProvider,
            model,
            // Empty string clears a prior local profile on this session.
            openaiProfileId: profileId || ''
          })
          onSessionUpdated?.(updated)
        }}
        onReasoningSettingsChange={async changes => {
          const runtimeProvider =
            changes.provider === 'local' ? 'openai' : changes.provider
          // Optimistic: picker follows runtimeSettings; avoid blocking on
          // a full model-catalog rediscover.
          setRuntimeSettings(prev =>
            prev
              ? {
                  ...prev,
                  ...(typeof changes.reasoningEffort === 'string'
                    ? { reasoningEffort: changes.reasoningEffort }
                    : {}),
                  ...(typeof changes.reasoningFast === 'boolean'
                    ? { reasoningFast: changes.reasoningFast }
                    : {})
                }
              : prev
          )
          const updatedSettings = await client.updateRuntimeSettings({
            ...(isDraftSession
              ? { provider: runtimeProvider, model: changes.model }
              : {}),
            reasoningEffort: changes.reasoningEffort,
            reasoningFast: changes.reasoningFast
          })
          setRuntimeSettings(updatedSettings)
          if (!isDraftSession && sessionId) {
            const updated = await client.updateSession(sessionId, {
              provider: runtimeProvider,
              model: changes.model
            })
            onSessionUpdated?.(updated)
          }
          void loadModelOptions()
        }}
        onPlanModeChange={async planMode => {
          setRuntimeSettings(
            await client.updateRuntimeSettings({ planMode })
          )
        }}
      />
    </>
  )
}
