import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSkill,
  McpServer,
  RuntimeSettings,
  ServerSystemInfo,
  SessionSandboxStatus,
  Specialist
} from '@sandwalk/agent-ui-core'
import { ArrowUp, ListChecks, Mic, Square, X } from 'lucide-react'

import { ComposerModelPicker } from '@/components/agents/composer/ComposerModelPicker'
import { planModeAccent } from '@/components/agents/composer/ComposerModeMenu'
import { ComposerPlusMenu } from '@/components/agents/composer/ComposerPlusMenu'
import { ComposerTokenUsage } from '@/components/agents/composer/ComposerTokenUsage'
import {
  type SandboxActionPhase,
  type SandboxComputeChange
} from '@/components/agents/composer/sandbox-utils'
import { openPlusMenu } from '@/components/agents/empty-start'
import { SpecialistAvatar } from '@/components/agents/SpecialistsView'
import { Button } from '@/components/ui/button'
import {
  type ComposerModelOption,
  type ComposerModelPreferences,
  resolveComposerModelOption
} from '@/lib/composer-models'
import { cn } from '@/lib/utils'

export function ComposerToolbar({
  running,
  showStopButton,
  sendDisabled = false,
  modelOptions,
  runtimeSettings,
  skills = [],
  mcpServers = [],
  onPickSkill,
  onPickMcp,
  specialists,
  selectedSpecialistId,
  sandboxStatus,
  sandboxPhase,
  tokenUsage,
  compactBusy = false,
  onCompact,
  showMic = false,
  voiceReady = false,
  voiceBusy = null,
  onVoiceToggle,
  onUpload,
  onModelSelect,
  onReasoningSettingsChange,
  onSpecialistSelect,
  onCreateSpecialist,
  onManageSpecialists,
  onAddModels,
  onLoadModelPreferences,
  onToggleModelFavorite,
  onFocusComposer,
  onSandboxBackendSelect,
  onSandboxComputeChange,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart,
  onLoadLocalSystem,
  onRefreshSandbox,
  onPlanModeChange,
  onStop,
  embedded = false,
  client
}: {
  running: boolean
  showStopButton: boolean
  sendDisabled?: boolean
  modelOptions: ComposerModelOption[]
  runtimeSettings: RuntimeSettings | null
  skills?: AgentSkill[]
  mcpServers?: McpServer[]
  onPickSkill?: (skill: AgentSkill) => void
  onPickMcp?: (server: McpServer) => void
  specialists: Specialist[]
  selectedSpecialistId: string | null
  sandboxStatus: SessionSandboxStatus | null
  sandboxPhase: SandboxActionPhase
  tokenUsage: { inputTokens: number; outputTokens: number }
  compactBusy?: boolean
  onCompact?: () => void | Promise<void>
  showMic?: boolean
  voiceReady?: boolean
  voiceBusy?: string | null
  onVoiceToggle?: () => void
  onUpload: (files: FileList) => void
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
  onFocusComposer?: () => void
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
  onStop: () => void
  /**
   * Cuando true, agrega `mt-4` (16 px) al toolbar. En split view (embedded)
   * ese aire garantiza el gap con la última línea del textarea AUNQUE el
   * texto scrollee — el padding vive fuera del editor, no se pierde con el
   * overflow interno.
   */
  embedded?: boolean
  client?: LocalAgentClient
}) {
  const planMode = Boolean(runtimeSettings?.planMode)
  const selectedSpecialist =
    specialists.find(item => item.id === selectedSpecialistId) || null

  return (
    <div
      className={cn(
        'flex min-w-0 items-center justify-between gap-2 px-0.5',
        embedded && 'mt-4'
      )}
    >
      <div className="flex h-7 min-w-0 flex-1 items-center gap-2">
        <ComposerPlusMenu
          runtimeSettings={runtimeSettings}
          skills={skills}
          mcpServers={mcpServers}
          specialists={specialists}
          selectedSpecialistId={selectedSpecialistId}
          sandboxStatus={sandboxStatus}
          sandboxPhase={sandboxPhase}
          onUpload={onUpload}
          onPlanModeChange={onPlanModeChange}
          onPickSkill={onPickSkill}
          onPickMcp={onPickMcp}
          onSpecialistSelect={onSpecialistSelect}
          onCreateSpecialist={onCreateSpecialist}
          onManageSpecialists={onManageSpecialists}
          onSandboxBackendSelect={onSandboxBackendSelect}
          onSandboxComputeChange={onSandboxComputeChange}
          onSandboxStart={onSandboxStart}
          onSandboxStop={onSandboxStop}
          onSandboxRestart={onSandboxRestart}
          onLoadLocalSystem={onLoadLocalSystem}
          onRefreshSandbox={onRefreshSandbox}
        />
        {planMode && onPlanModeChange ? (
          <span
            className={cn(
              'inline-flex h-7 shrink-0 items-center gap-1 rounded-full pl-2.5 pr-1 text-xs font-medium',
              planModeAccent.chip
            )}
          >
            <ListChecks className="size-3.5" />
            Plan
            <button
              type="button"
              aria-label="Turn off plan mode"
              className="hover:bg-black/10 inline-flex size-4 items-center justify-center rounded-full dark:hover:bg-white/10"
              onClick={() => void onPlanModeChange(false)}
            >
              <X className="size-3" />
            </button>
          </span>
        ) : null}
        {selectedSpecialist ? (
          <span
            data-testid="composer-selected-specialist-chip"
            className="border-border/70 bg-muted/60 text-foreground inline-flex h-7 shrink-0 items-center gap-1.5 rounded-full border pl-1.5 pr-1 text-xs font-medium"
          >
            <button
              type="button"
              onClick={() => openPlusMenu('specialist')}
              className="inline-flex items-center gap-1.5"
              title={`Active specialist: ${selectedSpecialist.name}${selectedSpecialist.roleLabel ? ` · ${selectedSpecialist.roleLabel}` : ''}`}
            >
              <SpecialistAvatar
                color={selectedSpecialist.color}
                icon={selectedSpecialist.icon}
                avatarUrl={selectedSpecialist.avatarUrl}
                slug={selectedSpecialist.slug}
                className="size-5"
              />
              <span className="max-w-[8.5rem] truncate">
                {selectedSpecialist.name}
              </span>
            </button>
            {onSpecialistSelect ? (
              <button
                type="button"
                aria-label={`Clear specialist ${selectedSpecialist.name}`}
                className="text-muted-foreground hover:text-foreground hover:bg-black/10 inline-flex size-4 items-center justify-center rounded-full dark:hover:bg-white/10"
                onClick={() => void onSpecialistSelect(null)}
              >
                <X className="size-3" />
              </button>
            ) : null}
          </span>
        ) : null}
        <ComposerModelPicker
          modelOptions={modelOptions}
          runtimeSettings={runtimeSettings}
          onModelSelect={onModelSelect}
          onReasoningSettingsChange={onReasoningSettingsChange}
          onAddModels={onAddModels}
          onLoadModelPreferences={onLoadModelPreferences}
          onToggleModelFavorite={onToggleModelFavorite}
          onFocusComposer={onFocusComposer}
          client={client}
        />
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <ComposerTokenUsage
          tokenUsage={tokenUsage}
          contextWindow={
            resolveComposerModelOption(modelOptions, runtimeSettings)
              ?.contextWindow
          }
          compactDisabled={running}
          compactBusy={compactBusy}
          onCompact={onCompact}
        />
        {showMic ? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className={cn(
              'size-7 shrink-0 rounded-full',
              voiceBusy && 'opacity-60',
              !voiceReady && 'opacity-40'
            )}
            disabled={Boolean(voiceBusy)}
            onClick={onVoiceToggle}
            title={
              voiceBusy ||
              (voiceReady
                ? 'Start local voice dictation'
                : 'Configure Voice Input in Settings')
            }
            aria-label={
              voiceReady
                ? 'Start dictation'
                : 'Configure Voice Input in Settings'
            }
            aria-disabled={!voiceReady}
          >
            <Mic className="size-4" />
          </Button>
        ) : null}
        <Button
          type={showStopButton ? 'button' : 'submit'}
          size="icon"
          disabled={!showStopButton && sendDisabled}
          className={cn(
            'size-7 rounded-full shadow-none',
            planMode
              ? planModeAccent.send
              : 'bg-foreground text-background hover:bg-foreground/90 [&_svg]:text-background'
          )}
          onClick={showStopButton ? onStop : undefined}
          aria-label={
            showStopButton ? 'Stop' : running ? 'Queue message' : 'Send'
          }
          title={showStopButton ? 'Stop' : running ? 'Queue' : 'Send'}
        >
          {showStopButton ? (
            <Square className="size-3 fill-current" />
          ) : (
            <ArrowUp className="size-4" strokeWidth={2.5} />
          )}
        </Button>
      </div>
    </div>
  )
}
