import type {
  RuntimeSettings,
  ServerSystemInfo,
  SessionSandboxStatus,
  Specialist
} from '@sandwalk/agent-ui-core'
import { ArrowUp, Mic, Plus, Square } from 'lucide-react'
import { useRef } from 'react'

import { ComposerModelPicker } from '@/components/agents/composer/ComposerModelPicker'
import {
  ComposerModeMenu,
  planModeAccent
} from '@/components/agents/composer/ComposerModeMenu'
import { ComposerSandboxPicker } from '@/components/agents/composer/ComposerSandboxPicker'
import { ComposerSpecialistPicker } from '@/components/agents/composer/ComposerSpecialistPicker'
import { ComposerTokenUsage } from '@/components/agents/composer/ComposerTokenUsage'
import {
  type SandboxActionPhase,
  type SandboxComputeChange
} from '@/components/agents/composer/sandbox-utils'
import { Button } from '@/components/ui/button'
import {
  type ComposerModelOption,
  resolveComposerModelOption
} from '@/lib/composer-models'
import { cn } from '@/lib/utils'

export function ComposerToolbar({
  running,
  showStopButton,
  sendDisabled = false,
  modelOptions,
  runtimeSettings,
  specialists,
  selectedSpecialistId,
  sandboxStatus,
  sandboxPhase,
  tokenUsage,
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
  onSandboxBackendSelect,
  onSandboxComputeChange,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart,
  onLoadLocalSystem,
  onPlanModeChange,
  onStop
}: {
  running: boolean
  showStopButton: boolean
  sendDisabled?: boolean
  modelOptions: ComposerModelOption[]
  runtimeSettings: RuntimeSettings | null
  specialists: Specialist[]
  selectedSpecialistId: string | null
  sandboxStatus: SessionSandboxStatus | null
  sandboxPhase: SandboxActionPhase
  tokenUsage: { inputTokens: number; outputTokens: number }
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
  onPlanModeChange?: (planMode: boolean) => Promise<void>
  onStop: () => void
}) {
  const uploadRef = useRef<HTMLInputElement | null>(null)
  const planMode = Boolean(runtimeSettings?.planMode)

  return (
    <div className="flex min-w-0 items-center justify-between gap-2 px-0.5">
      <div className="flex min-w-0 flex-1 items-center gap-1 overflow-hidden">
        <input
          ref={uploadRef}
          type="file"
          multiple
          hidden
          onChange={event => {
            if (event.target.files) onUpload(event.target.files)
            event.target.value = ''
          }}
        />
        <Button
          variant="ghost"
          size="icon"
          className="size-7 shrink-0 rounded-full"
          type="button"
          onClick={() => uploadRef.current?.click()}
        >
          <Plus className="size-4" />
        </Button>
        {onPlanModeChange ? (
          <ComposerModeMenu
            runtimeSettings={runtimeSettings}
            onPlanModeChange={onPlanModeChange}
          />
        ) : null}
        <ComposerModelPicker
          modelOptions={modelOptions}
          runtimeSettings={runtimeSettings}
          onModelSelect={onModelSelect}
          onReasoningSettingsChange={onReasoningSettingsChange}
          onAddModels={onAddModels}
        />
        {onSpecialistSelect ? (
          <ComposerSpecialistPicker
            specialists={specialists}
            selectedSpecialistId={selectedSpecialistId}
            onSpecialistSelect={onSpecialistSelect}
            onCreateSpecialist={onCreateSpecialist}
            onManageSpecialists={onManageSpecialists}
          />
        ) : null}
        {onSandboxBackendSelect ? (
          <ComposerSandboxPicker
            sandboxStatus={sandboxStatus}
            sandboxPhase={sandboxPhase}
            onSandboxBackendSelect={onSandboxBackendSelect}
            onSandboxComputeChange={onSandboxComputeChange}
            onSandboxStart={onSandboxStart}
            onSandboxStop={onSandboxStop}
            onSandboxRestart={onSandboxRestart}
            onLoadLocalSystem={onLoadLocalSystem}
          />
        ) : null}
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <ComposerTokenUsage
          tokenUsage={tokenUsage}
          contextWindow={
            resolveComposerModelOption(modelOptions, runtimeSettings)
              ?.contextWindow
          }
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
