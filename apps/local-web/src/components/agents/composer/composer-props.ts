import type {
  AgentSession,
  AgentSkill,
  AgentSkillDetail,
  McpServer,
  RuntimeSettings,
  ServerSystemInfo,
  SessionSandboxStatus,
  Specialist,
  WorkspaceFile
} from '@sandwalk/agent-ui-core'
import type { MutableRefObject } from 'react'

import {
  type SandboxActionPhase,
  type SandboxComputeChange
} from '@/components/agents/composer/sandbox-utils'
import {
  type ComposerModelOption,
  type ComposerModelPreferences
} from '@/lib/composer-models'

export type { SandboxActionPhase, SandboxComputeChange }

export type ComposerProps = {
  value: string
  running: boolean
  skills: AgentSkill[]
  mcpServers?: McpServer[]
  skillChips: string[]
  fileChips?: string[]
  workspaceFiles?: WorkspaceFile[]
  modelOptions: ComposerModelOption[]
  specialists?: Specialist[]
  selectedSpecialistId?: string | null
  sandboxStatus?: SessionSandboxStatus | null
  sandboxPhase?: SandboxActionPhase
  showAura?: boolean
  autoFocus?: boolean
  focusKey?: string | null
  /** Workspace paths to attach as upload-style previews when the session opens. */
  pendingAttachmentsRef?: MutableRefObject<{
    sessionId: string
    paths: string[]
  } | null>
  /** Resolve mime + optional preview URL for a workspace path already on disk. */
  onResolveAttachment?: (path: string) => Promise<{
    name: string
    contentType: string
    previewUrl?: string
  } | null>
  onChange: (value: string) => void
  onLiveDraftChange?: (value: string) => void
  onSkillChipsChange: (skills: string[]) => void
  onFileChipsChange?: (files: string[]) => void
  onSend: (value: string) => void
  onStop: () => void
  /** Upload files into the session workspace; returns paths used for send. */
  onUpload: (
    files: File[]
  ) => Promise<Array<{ path: string; name: string; mimeType?: string }>>
  onLoadSkill: (name: string) => Promise<AgentSkillDetail>
  onOpenFile?: (path: string) => void
  /** Ensure workspace file index is ready for @ mentions (no Files panel required). */
  onEnsureWorkspaceFiles?: () => void | Promise<void>
  runtimeSettings: RuntimeSettings | null
  tokenUsage: { inputTokens: number; outputTokens: number }
  compactBusy?: boolean
  onCompact?: () => void | Promise<void>
  onModelSelect: (
    provider: string,
    model: string,
    profileId?: string | null
  ) => Promise<void>
  onReasoningSettingsChange?: (changes: {
    provider: string
    model: string
    reasoningEffort?: string
    reasoningFast?: boolean
  }) => Promise<void>
  onSpecialistSelect?: (specialistId: string | null) => void | Promise<void>
  onCreateSpecialist?: () => void
  onManageSpecialists?: () => void
  onAddModels?: () => void
  onLoadModelPreferences?: () => Promise<ComposerModelPreferences>
  onToggleModelFavorite?: (option: ComposerModelOption) => Promise<{
    favorite: boolean
    favorites: string[]
  }>
  onSandboxBackendSelect?: (
    backend: 'builtin' | 'modal'
  ) => void | Promise<void>
  onSandboxComputeChange?: (
    changes: SandboxComputeChange
  ) => void | Promise<void>
  onSandboxStart?: () => void | Promise<void>
  onSandboxStop?: () => void | Promise<void>
  onSandboxRestart?: () => void | Promise<void>
  onLoadLocalSystem?: () => Promise<ServerSystemInfo | null>
  onRefreshSandbox?: () => void | Promise<void>
  onPlanModeChange?: (planMode: boolean) => Promise<void>
  editingQueued?: boolean
  onCancelEditQueued?: () => void
  /**
   * Cuando `true`, el composer se pinta sin chip propio: sin `bg-card`, sin
   * `rounded-3xl`, sin `border` externo, sin `shadow`. Diseñado para
   * embeberlo como parte inferior de un contenedor exterior (ej. un panel
   * del split view) que ya aporta su propio borde y fondo. El separator
   * arriba del composer lo dibuja el contenedor exterior.
   */
  embedded?: boolean
  mentionChats?: AgentSession[]
  placeholder?: string
}
