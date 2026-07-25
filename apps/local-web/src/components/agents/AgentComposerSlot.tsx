import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
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
import type { NavigateFunction } from 'react-router-dom'

import {
  Composer,
  type SandboxActionPhase
} from '@/components/agents/Composer'
import { type SandboxComputeChange } from '@/components/agents/composer/sandbox-utils'
import { QueuedMessages } from '@/components/agents/QueuedMessages'
import {
  resolveComposerModelOption,
  type ComposerModelOption
} from '@/lib/composer-models'
import {
  contentTypeFromPath,
  needsAttachmentPreview
} from '@/lib/attachment-mime'
import { mediaObjectUrlFromFile } from '@/lib/media-src'
import {
  modelSupportsMultimodalKind,
  multimodalKindForFile,
  unsupportedMultimodalHint
} from '@/lib/multimodal-attach'
import type { QueuedMessage } from '@/lib/sessions'
import { toast } from 'sonner'

type AgentComposerSlotProps = {
  sessionId: string | null
  session: AgentSession | null
  client: LocalAgentClient
  navigate: NavigateFunction
  pendingAttachmentsRef: MutableRefObject<{
    sessionId: string
    paths: string[]
  } | null>
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
  runtimeSettings: RuntimeSettings | null
  tokenUsage: { inputTokens: number; outputTokens: number }
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
  setRuntimeSettings: Dispatch<SetStateAction<RuntimeSettings | null>>
  loadModelOptions: () => Promise<void>
}

export function AgentComposerSlot({
  sessionId,
  session,
  client,
  navigate,
  pendingAttachmentsRef,
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
  runtimeSettings,
  tokenUsage,
  selectSessionSpecialist,
  selectSessionSandboxBackend,
  updateSessionSandboxCompute,
  startSessionSandbox,
  stopSessionSandbox,
  restartSessionSandbox,
  setRuntimeSettings,
  loadModelOptions
}: AgentComposerSlotProps) {
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
        key={sessionId ?? 'empty-composer'}
        value={composer}
        running={runActive}
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
        autoFocus
        focusKey={sessionId}
        pendingAttachmentsRef={pendingAttachmentsRef}
        onResolveAttachment={async path => {
          if (!sessionId) return null
          const name = path.split('/').at(-1) || path
          const contentType = contentTypeFromPath(path)
          if (!needsAttachmentPreview(contentType, path)) {
            return { name, contentType }
          }
          try {
            const file = await client.readFile(sessionId, path)
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
        onSend={handleComposerSend}
        onStop={() => void handleStop()}
        onLoadSkill={loadSkillDetail}
        onUpload={async files => {
          if (!sessionId) return []
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
            files.map(file => client.uploadFile(sessionId, file))
          )
          setWorkspaceVersion(current => current + 1)
          return uploaded.map(item => ({
            path: item.path,
            name: item.path.split('/').at(-1) || item.path,
            mimeType: item.mimeType
          }))
        }}
        runtimeSettings={runtimeSettings}
        tokenUsage={tokenUsage}
        onSpecialistSelect={selectSessionSpecialist}
        onCreateSpecialist={() => navigate('/dashboard/specialists/new')}
        onManageSpecialists={() => navigate('/dashboard/specialists')}
        onAddModels={() => navigate('/dashboard/models')}
        onSandboxBackendSelect={selectSessionSandboxBackend}
        onSandboxComputeChange={changes =>
          void updateSessionSandboxCompute(changes)
        }
        onSandboxStart={() => void startSessionSandbox()}
        onSandboxStop={() => void stopSessionSandbox()}
        onSandboxRestart={() => void restartSessionSandbox()}
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
          setRuntimeSettings(
            await client.updateRuntimeSettings({
              provider: runtimeProvider,
              model
            })
          )
        }}
        onReasoningSettingsChange={async changes => {
          const runtimeProvider =
            changes.provider === 'local' ? 'openai' : changes.provider
          setRuntimeSettings(
            await client.updateRuntimeSettings({
              provider: runtimeProvider,
              model: changes.model,
              reasoningEffort: changes.reasoningEffort,
              reasoningFast: changes.reasoningFast
            })
          )
          await loadModelOptions()
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
