import type {
  RuntimeSettings,
  ServerSystemInfo,
  SessionSandboxStatus,
  Specialist
} from '@sandwalk/agent-ui-core'
import { ArrowUp, Plus, Square } from 'lucide-react'
import { useRef } from 'react'

import { ComposerModelPicker } from '@/components/agents/composer/ComposerModelPicker'
import { ComposerSandboxPicker } from '@/components/agents/composer/ComposerSandboxPicker'
import { ComposerSpecialistPicker } from '@/components/agents/composer/ComposerSpecialistPicker'
import { ComposerTokenUsage } from '@/components/agents/composer/ComposerTokenUsage'
import {
  type SandboxActionPhase,
  type SandboxComputeChange
} from '@/components/agents/composer/sandbox-utils'
import { Button } from '@/components/ui/button'
import { type ComposerModelOption } from '@/lib/composer-models'

export function ComposerToolbar({
  running,
  showStopButton,
  modelOptions,
  runtimeSettings,
  specialists,
  selectedSpecialistId,
  sandboxStatus,
  sandboxPhase,
  tokenUsage,
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
  onStop
}: {
  running: boolean
  showStopButton: boolean
  modelOptions: ComposerModelOption[]
  runtimeSettings: RuntimeSettings | null
  specialists: Specialist[]
  selectedSpecialistId: string | null
  sandboxStatus: SessionSandboxStatus | null
  sandboxPhase: SandboxActionPhase
  tokenUsage: { inputTokens: number; outputTokens: number }
  onUpload: (files: FileList) => Promise<void>
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
  onStop: () => void
}) {
  const uploadRef = useRef<HTMLInputElement | null>(null)

  return (
    <div className="flex min-w-0 items-center justify-between gap-2 px-0.5">
      <div className="flex min-w-0 flex-1 items-center gap-1 overflow-hidden">
        <input
          ref={uploadRef}
          type="file"
          multiple
          hidden
          onChange={event => {
            if (event.target.files) void onUpload(event.target.files)
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
        <ComposerTokenUsage tokenUsage={tokenUsage} />
        <Button
          type={showStopButton ? 'button' : 'submit'}
          size="icon"
          className="bg-foreground text-background hover:bg-foreground/90 size-7 rounded-full shadow-none [&_svg]:text-background"
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
