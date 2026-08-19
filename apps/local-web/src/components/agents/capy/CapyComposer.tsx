import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  AgentSkill,
  BackendHealth,
  McpServer,
  RuntimeSettings
} from '@sandwalk/agent-ui-core'

import { Composer } from '@/components/agents/Composer'
import {
  type ComposerModelOption,
  resolveComposerModelOption
} from '@/lib/composer-models'
import {
  modelSupportsMultimodalKind,
  multimodalKindForFile,
  unsupportedMultimodalHint
} from '@/lib/multimodal-attach'
import { contentTypeFromPath, needsAttachmentPreview } from '@/lib/attachment-mime'
import { mediaObjectUrlFromFile } from '@/lib/media-src'

export function CapyComposer({
  client,
  session,
  health,
  value,
  running,
  chats,
  skills,
  mcpServers,
  modelOptions,
  runtimeSettings,
  tokenUsage,
  onChange,
  onSend,
  onStop,
  onSessionUpdated,
  onMessagesReloaded,
  setRuntimeSettings,
  loadModelOptions,
  captureWindowDrops = false,
  onDropActiveChange
}: {
  client: LocalAgentClient
  session: AgentSession | null
  health: BackendHealth | null
  value: string
  running: boolean
  chats: AgentSession[]
  skills: AgentSkill[]
  mcpServers: McpServer[]
  modelOptions: ComposerModelOption[]
  runtimeSettings: RuntimeSettings | null
  tokenUsage: { inputTokens: number; outputTokens: number }
  onChange: (value: string) => void
  onSend: (value: string) => void
  onStop: () => void
  onSessionUpdated: (session: AgentSession) => void
  onMessagesReloaded: () => void
  setRuntimeSettings: (
    value: RuntimeSettings | null | ((current: RuntimeSettings | null) => RuntimeSettings | null)
  ) => void
  loadModelOptions: () => Promise<void>
  captureWindowDrops?: boolean
  onDropActiveChange?: (active: boolean) => void
}) {
  const navigate = useNavigate()
  const [compactBusy, setCompactBusy] = useState(false)
  const composerRuntime = useMemo(() => {
    if (!runtimeSettings) return null
    if (!session?.model) return runtimeSettings
    return {
      ...runtimeSettings,
      provider: session.provider || runtimeSettings.provider,
      model: session.model,
      openaiProfileId:
        session.openaiProfileId ?? runtimeSettings.openaiProfileId ?? null
    }
  }, [runtimeSettings, session])

  if (!health) return null

  return (
    <Composer
      value={value}
      running={running}
      showAura={false}
      autoFocus
      focusKey={session?.id ?? 'capy'}
      skills={skills}
      mcpServers={mcpServers}
      skillChips={[]}
      fileChips={[]}
      mentionChats={chats}
      placeholder="Ask Capy..."
      captureWindowDrops={captureWindowDrops}
      onDropActiveChange={onDropActiveChange}
      modelOptions={modelOptions}
      runtimeSettings={composerRuntime}
      tokenUsage={tokenUsage}
      compactBusy={compactBusy}
      onChange={onChange}
      onSkillChipsChange={() => undefined}
      onSend={onSend}
      onStop={onStop}
      onLoadSkill={name => client.getSkill(name)}
      onCompact={
        session
          ? async () => {
              if (compactBusy || running) return
              setCompactBusy(true)
              try {
                await client.compactSession(session.id)
                onMessagesReloaded()
              } catch (cause) {
                toast.error(
                  cause instanceof Error ? cause.message : 'Compact failed'
                )
              } finally {
                setCompactBusy(false)
              }
            }
          : undefined
      }
      onUpload={async files => {
        if (!session) return []
        const activeModel = resolveComposerModelOption(modelOptions, {
          provider: composerRuntime?.provider || '',
          model: composerRuntime?.model || '',
          openaiProfileId: composerRuntime?.openaiProfileId ?? null
        })
        for (const file of files) {
          const kind = multimodalKindForFile(file)
          if (kind && !modelSupportsMultimodalKind(activeModel, kind)) {
            toast.message(unsupportedMultimodalHint(kind))
          }
        }
        const uploaded = await Promise.all(
          files.map(file => client.uploadFile(session.id, file))
        )
        return uploaded.map(item => ({
          path: item.path,
          name: item.path.split('/').at(-1) || item.path,
          mimeType: item.mimeType
        }))
      }}
      onResolveAttachment={async path => {
        if (!session) return null
        const name = path.split('/').at(-1) || path
        const contentType = contentTypeFromPath(path)
        if (!needsAttachmentPreview(contentType, path)) {
          return { name, contentType }
        }
        try {
          const file = await client.readFile(session.id, path)
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
      onAddModels={() => navigate('/dashboard/models')}
      onLoadModelPreferences={() => client.getModelPreferences()}
      onToggleModelFavorite={option =>
        client.toggleModelFavorite({
          provider: option.provider,
          model: option.model,
          profileId: option.profileId
        })
      }
      onModelSelect={async (provider, model, profileId) => {
        if (profileId) {
          try {
            await client.updateModelProfile(profileId, { setActive: true })
          } catch {
            /* best-effort */
          }
        }
        const runtimeProvider =
          provider === 'local' || profileId ? 'openai' : provider
        if (session) {
          const updated = await client.updateSession(session.id, {
            provider: runtimeProvider,
            model,
            openaiProfileId: profileId || ''
          })
          onSessionUpdated(updated)
        }
        setRuntimeSettings(
          await client.updateRuntimeSettings({
            provider: runtimeProvider,
            model
          })
        )
        void loadModelOptions()
      }}
      onReasoningSettingsChange={async changes => {
        const runtimeProvider =
          changes.provider === 'local' ? 'openai' : changes.provider
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
          provider: runtimeProvider,
          model: changes.model,
          reasoningEffort: changes.reasoningEffort,
          reasoningFast: changes.reasoningFast
        })
        setRuntimeSettings(updatedSettings)
        if (session) {
          const updated = await client.updateSession(session.id, {
            provider: runtimeProvider,
            model: changes.model
          })
          onSessionUpdated(updated)
        }
        void loadModelOptions()
      }}
    />
  )
}
