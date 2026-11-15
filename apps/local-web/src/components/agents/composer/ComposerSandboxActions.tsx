import type { SessionSandboxStatus } from '@sandwalk/agent-ui-core'
import { Loader, RefreshCw } from 'lucide-react'

import {
  type SandboxActionPhase,
  type SandboxDraft
} from '@/components/agents/composer/sandbox-utils'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function ComposerSandboxActions({
  sandboxStatus,
  sandboxDraft,
  sandboxPhase,
  sandboxDraftDirty,
  sandboxConfirming,
  appliedSandboxBackend,
  onConfirm,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart,
  inCard = false
}: {
  sandboxStatus: SessionSandboxStatus | null
  sandboxDraft: SandboxDraft
  sandboxPhase: SandboxActionPhase
  sandboxDraftDirty: boolean
  sandboxConfirming: boolean
  appliedSandboxBackend: 'builtin' | 'modal'
  onConfirm: () => void | Promise<void>
  onSandboxStart?: () => void | Promise<void>
  onSandboxStop?: () => void | Promise<void>
  onSandboxRestart?: () => void | Promise<void>
  /**
   * Inside the sandbox card: the row above already offers Start and Stop, so
   * keep only Confirm and Restart, sized to their labels at the row's end.
   */
  inCard?: boolean
}) {
  const showModalControls =
    sandboxDraft.backend === 'modal' &&
    sandboxStatus?.modalConfigured === true &&
    appliedSandboxBackend === 'modal'

  return (
    <>
      <div
        className={cn(
          'flex items-center gap-1',
          inCard ? 'shrink-0 flex-row-reverse' : 'pt-0.5'
        )}
      >
        <Button
          type="button"
          size="sm"
          className={cn(
            'h-7 text-[11px]',
            inCard ? 'px-4' : 'flex-1 px-2'
          )}
          disabled={
            sandboxPhase !== 'idle' ||
            sandboxConfirming ||
            !sandboxDraftDirty ||
            (sandboxDraft.backend === 'modal' &&
              sandboxStatus?.modalConfigured !== true)
          }
          onClick={() => void onConfirm()}
        >
          {sandboxConfirming ? (
            <>
              <Loader className="size-3 animate-spin" />
              Applying…
            </>
          ) : (
            'Confirm'
          )}
        </Button>

        {showModalControls ? (
          sandboxPhase !== 'idle' ||
          sandboxStatus.status === 'starting' ||
          sandboxStatus.status === 'stopping' ? (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="h-7 px-2 text-[11px]"
              disabled
            >
              <Loader className="size-3 animate-spin" />
            </Button>
          ) : sandboxStatus.status === 'running' ? (
            <>
              {inCard ? null : (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="text-destructive hover:text-destructive h-7 px-2 text-[11px]"
                  onClick={() => void onSandboxStop?.()}
                >
                  Stop
                </Button>
              )}
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="h-7 px-2"
                aria-label="Restart sandbox"
                title="Restart sandbox"
                onClick={() => void onSandboxRestart?.()}
              >
                <RefreshCw className="size-3" />
              </Button>
            </>
          ) : inCard ? null : (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="h-7 px-2 text-[11px]"
              disabled={
                sandboxStatus.status === 'unavailable' ||
                !onSandboxStart ||
                sandboxConfirming
              }
              onClick={() => void onSandboxStart?.()}
            >
              Start
            </Button>
          )
        ) : null}
      </div>

      {!inCard &&
      sandboxStatus?.detail &&
      sandboxStatus.status !== 'running' &&
      appliedSandboxBackend === 'modal' ? (
        <p className="text-muted-foreground px-0.5 text-[10px] leading-snug">
          {sandboxStatus.detail}
        </p>
      ) : null}
    </>
  )
}
