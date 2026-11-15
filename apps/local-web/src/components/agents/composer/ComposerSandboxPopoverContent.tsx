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
  onSandboxRestart,
  variant = 'chooser'
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
  /**
   * `chooser` (the + menu) decides whether the chat uses Modal at all.
   * `edit` (inside the sandbox card) is already about a Modal sandbox, so
   * it shows only that sandbox's settings.
   */
  variant?: 'chooser' | 'edit'
}) {
  const chooser = variant === 'chooser'
  const actions = (
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
      inCard={!chooser}
    />
  )
  return (
    <>
      {chooser ? <ComposerSandboxHeader onClose={onClose} /> : null}
      <div className={chooser ? 'space-y-1.5 p-2' : 'space-y-2.5 px-2.5 py-2.5'}>
        {chooser ? (
          <ComposerSandboxBackendToggle
            sandboxStatus={sandboxStatus}
            sandboxDraft={sandboxDraft}
            sandboxPhase={sandboxPhase}
            sandboxConfirming={sandboxConfirming}
            onClose={onClose}
            onDraftChange={onDraftChange}
          />
        ) : null}

        {chooser && sandboxDraft.backend === 'builtin' ? (
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
          wide={!chooser}
          footer={chooser ? undefined : actions}
        />

        {chooser ? actions : null}
      </div>
    </>
  )
}
