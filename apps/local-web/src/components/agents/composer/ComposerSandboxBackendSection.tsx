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
  return (
    <>
      <div className="inline-flex w-full rounded-md border p-0.5">
        <button
          type="button"
          disabled={sandboxPhase !== 'idle' || sandboxConfirming}
          onClick={() =>
            onDraftChange(current => ({
              ...current,
              backend: 'builtin'
            }))
          }
          className={cn(
            'flex flex-1 items-center justify-center gap-1 rounded px-1.5 py-1 text-[11px] font-medium transition-colors',
            sandboxDraft.backend === 'builtin'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
            (sandboxPhase !== 'idle' || sandboxConfirming) &&
              'cursor-not-allowed opacity-60'
          )}
        >
          <span className="bg-muted-foreground/40 size-1.5 rounded-full" />
          Local
        </button>
        {sandboxStatus?.modalConfigured !== true ? (
          <div className="text-muted-foreground flex flex-1 items-center justify-center gap-1 rounded px-1.5 py-1 text-[11px] opacity-60">
            <ModalGlyph className="size-3 opacity-70" />
            Modal
          </div>
        ) : (
          <button
            type="button"
            disabled={sandboxPhase !== 'idle' || sandboxConfirming}
            onClick={() =>
              onDraftChange(current => ({
                ...current,
                backend: 'modal'
              }))
            }
            className={cn(
              'flex flex-1 items-center justify-center gap-1 rounded px-1.5 py-1 text-[11px] font-medium transition-colors',
              sandboxDraft.backend === 'modal'
                ? 'bg-background text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
              (sandboxPhase !== 'idle' || sandboxConfirming) &&
                'cursor-not-allowed opacity-60'
            )}
          >
            <ModalGlyph className="size-3" />
            Modal
          </button>
        )}
      </div>

      {sandboxStatus?.modalConfigured !== true ? (
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
