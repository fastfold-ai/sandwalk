import type {
  ServerSystemInfo,
  SessionSandboxStatus
} from '@sandwalk/agent-ui-core'
import { Link } from 'react-router-dom'

import { ModalGlyph } from '@/components/agents/composer/ModalGlyph'
import {
  formatSandboxBytes,
  type SandboxActionPhase,
  type SandboxDraft
} from '@/components/agents/composer/sandbox-utils'
import { cn } from '@/lib/utils'

export function ComposerSandboxHeader({ onClose }: { onClose: () => void }) {
  return (
    <div className="flex items-center justify-between gap-2 border-b px-2.5 py-1.5">
      <span className="text-muted-foreground text-[10px] font-medium tracking-wide uppercase">
        Sandbox
      </span>
      <Link
        to="/dashboard/agent/sandbox"
        className="text-muted-foreground hover:text-foreground text-[10px] font-medium underline-offset-2 hover:underline"
        onClick={onClose}
      >
        Settings
      </Link>
    </div>
  )
}

/**
 * Local is the default and needs no configuring, so this is one switch for
 * the only thing to choose: run this chat's code in a Modal sandbox or not.
 */
export function ComposerSandboxBackendToggle({
  sandboxStatus,
  sandboxDraft,
  sandboxPhase,
  sandboxConfirming,
  onClose,
  onDraftChange
}: {
  sandboxStatus: SessionSandboxStatus | null
  sandboxDraft: SandboxDraft
  sandboxPhase: SandboxActionPhase
  sandboxConfirming: boolean
  onClose: () => void
  onDraftChange: (updater: (current: SandboxDraft) => SandboxDraft) => void
}) {
  const configured = sandboxStatus?.modalConfigured === true
  const on = configured && sandboxDraft.backend === 'modal'
  const disabled = !configured || sandboxPhase !== 'idle' || sandboxConfirming
  return (
    <>
      <div className="flex items-center justify-between gap-2 px-0.5 py-0.5">
        <span
          className={cn(
            'flex items-center gap-1.5 text-[11px] font-medium',
            !configured && 'text-muted-foreground'
          )}
        >
          <ModalGlyph className={cn('size-3', !configured && 'opacity-70')} />
          Modal sandbox
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-label="Use Modal sandbox"
          disabled={disabled}
          className={cn(
            'relative h-4 w-7 shrink-0 rounded-full transition-colors',
            on ? 'bg-foreground' : 'bg-muted-foreground/30',
            disabled && 'cursor-not-allowed opacity-60'
          )}
          onClick={() =>
            onDraftChange(current => ({
              ...current,
              backend: current.backend === 'modal' ? 'builtin' : 'modal'
            }))
          }
        >
          <span
            className={cn(
              'bg-background absolute top-0.5 left-0.5 size-3 rounded-full shadow-sm transition-transform',
              on && 'translate-x-3'
            )}
          />
        </button>
      </div>

      {!configured ? (
        <p className="text-muted-foreground px-0.5 text-[10px] leading-snug">
          Modal not set up.{' '}
          <Link
            to="/dashboard/agent/sandbox/modal"
            className="text-foreground font-medium underline underline-offset-2"
            onClick={onClose}
          >
            Set up
          </Link>
        </p>
      ) : null}
    </>
  )
}

export function ComposerSandboxLocalInfo({
  localSystem,
  localSystemLoading
}: {
  localSystem: ServerSystemInfo | null
  localSystemLoading: boolean
}) {
  return (
    <div className="bg-muted/30 space-y-1 rounded-md border border-border/60 px-2 py-1.5 text-[10px]">
      <p className="text-muted-foreground font-medium tracking-wide uppercase">
        This machine
      </p>
      {localSystemLoading && !localSystem ? (
        <p className="text-muted-foreground">Loading system info…</p>
      ) : localSystem ? (
        <div className="text-foreground space-y-0.5">
          <div className="flex items-start justify-between gap-2">
            <span className="text-muted-foreground">Chip</span>
            <span className="min-w-0 text-right leading-snug">
              {localSystem.chipName?.trim() ||
                localSystem.label ||
                `${localSystem.platform} · ${localSystem.arch}`}
            </span>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span className="text-muted-foreground">RAM</span>
            <span className="tabular-nums">
              {formatSandboxBytes(localSystem.ramUsedBytes)} /{' '}
              {formatSandboxBytes(localSystem.ramTotalBytes)}
            </span>
          </div>
          {localSystem.gpuCores != null ? (
            <div className="flex items-center justify-between gap-2">
              <span className="text-muted-foreground">GPU cores</span>
              <span className="tabular-nums">{localSystem.gpuCores}</span>
            </div>
          ) : null}
          <div className="flex items-center justify-between gap-2">
            <span className="text-muted-foreground">Arch</span>
            <span className="truncate">
              {localSystem.arch}
              {localSystem.osVersion ? ` · ${localSystem.osVersion}` : ''}
            </span>
          </div>
        </div>
      ) : (
        <p className="text-muted-foreground">
          Local Python environment on this computer.
        </p>
      )}
    </div>
  )
}
