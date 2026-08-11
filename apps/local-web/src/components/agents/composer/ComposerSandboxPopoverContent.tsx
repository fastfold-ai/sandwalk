import type {
  ServerSystemInfo,
  SessionSandboxStatus
} from '@sandwalk/agent-ui-core'

import { ComposerSandboxActions } from '@/components/agents/composer/ComposerSandboxActions'
import {
  ComposerSandboxBackendToggle,
  ComposerSandboxHeader,
  ComposerSandboxLocalInfo
} from '@/components/agents/composer/ComposerSandboxBackendSection'
import { ComposerSandboxModalConfig } from '@/components/agents/composer/ComposerSandboxModalConfig'
import {
  type SandboxActionPhase,
  type SandboxDraft
} from '@/components/agents/composer/sandbox-utils'

export function ComposerSandboxPopoverContent({
  sandboxStatus,
  sandboxPhase,
  sandboxDraft,
  sandboxDraftDirty,
  sandboxConfirming,
  appliedSandboxBackend,
  localSystem,
  localSystemLoading,
  onClose,
  onDraftChange,
  onConfirm,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart
}: {
  sandboxStatus: SessionSandboxStatus | null
  sandboxPhase: SandboxActionPhase
  sandboxDraft: SandboxDraft
  sandboxDraftDirty: boolean
  sandboxConfirming: boolean
  appliedSandboxBackend: 'builtin' | 'modal'
  localSystem: ServerSystemInfo | null
  localSystemLoading: boolean
  onClose: () => void
  onDraftChange: (
    updater: (current: SandboxDraft) => SandboxDraft
  ) => void
  onConfirm: () => void | Promise<void>
  onSandboxStart?: () => void | Promise<void>
  onSandboxStop?: () => void | Promise<void>
  onSandboxRestart?: () => void | Promise<void>
}) {
  return (
    <>
      <ComposerSandboxHeader onClose={onClose} />
      <div className="space-y-1.5 p-2">
        <ComposerSandboxBackendToggle
          sandboxStatus={sandboxStatus}
          sandboxDraft={sandboxDraft}
          sandboxPhase={sandboxPhase}
          sandboxConfirming={sandboxConfirming}
          onClose={onClose}
          onDraftChange={onDraftChange}
        />

        {sandboxDraft.backend === 'builtin' ? (
          <ComposerSandboxLocalInfo
            localSystem={localSystem}
            localSystemLoading={localSystemLoading}
          />
        ) : null}

        <ComposerSandboxModalConfig
          sandboxStatus={sandboxStatus}
          sandboxDraft={sandboxDraft}
          sandboxPhase={sandboxPhase}
          sandboxConfirming={sandboxConfirming}
          onDraftChange={onDraftChange}
        />

        <ComposerSandboxActions
          sandboxStatus={sandboxStatus}
          sandboxDraft={sandboxDraft}
          sandboxPhase={sandboxPhase}
          sandboxDraftDirty={sandboxDraftDirty}
          sandboxConfirming={sandboxConfirming}
          appliedSandboxBackend={appliedSandboxBackend}
          onConfirm={onConfirm}
          onSandboxStart={onSandboxStart}
          onSandboxStop={onSandboxStop}
          onSandboxRestart={onSandboxRestart}
        />
      </div>
    </>
  )
}
