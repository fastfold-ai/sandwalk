import type {
  ServerSystemInfo,
  SessionSandboxStatus
} from '@sandwalk/agent-ui-core'
import { Container, Minus, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { ComposerSandboxPicker } from '@/components/agents/composer/ComposerSandboxPicker'
import { ModalGlyph } from '@/components/agents/composer/ModalGlyph'
import {
  formatSandboxElapsed,
  type SandboxActionPhase,
  sandboxBackendName,
  type SandboxComputeChange,
  sandboxIsLive,
  sandboxLifecycleLine,
  sandboxLifecycleSummary,
  sandboxSpecs,
  sandboxStopLine,
  sandboxStoppedOnItsOwn,
  sandboxStopSummary,
  sandboxTransitionLabel
} from '@/components/agents/composer/sandbox-utils'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

/** Lit cells of a 3x3 grid, row by row. Eight steps, one turn of the shape. */
const DOT_FRAMES = [
  '000101101',
  '100100011',
  '100110010',
  '110110001',
  '010111101',
  '011011100',
  '001011010',
  '001001110'
] as const
const DOT_FRAME_MS = 175

function ActivityDots() {
  const [frame, setFrame] = useState(0)

  useEffect(() => {
    const timer = window.setInterval(
      () => setFrame(current => (current + 1) % DOT_FRAMES.length),
      DOT_FRAME_MS
    )
    return () => window.clearInterval(timer)
  }, [])

  return (
    <span
      className="text-muted-foreground grid shrink-0 grid-cols-3 gap-[1.5px]"
      aria-hidden
    >
      {DOT_FRAMES[frame].split('').map((cell, index) => (
        <span
          key={index}
          className={cn(
            'size-[2px] rounded-full bg-current',
            cell === '0' && 'opacity-0'
          )}
        />
      ))}
    </span>
  )
}

/**
 * Floats above the composer, over the transcript, so it takes no layout
 * space: a "1 Sandbox" chip, and a full-width card when it is open. The card
 * shows what is running, when it will stop, and the settings to change it.
 * A sandbox Modal ended on its own stays listed as stopped, with the reason.
 */
export function ComposerSandboxChip({
  sandboxStatus = null,
  sandboxPhase = 'idle',
  embedded = false,
  onSandboxBackendSelect,
  onSandboxComputeChange,
  onSandboxStart,
  onSandboxStop,
  onSandboxRestart,
  onLoadLocalSystem,
  onRefreshSandbox
}: {
  sandboxStatus?: SessionSandboxStatus | null
  sandboxPhase?: SandboxActionPhase
  /** Split-view composer: match its horizontal inset. */
  embedded?: boolean
  /** Enables Edit: the backend and compute settings, inside the card. */
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
}) {
  const live = sandboxIsLive(sandboxStatus, sandboxPhase)
  const stopped = sandboxStoppedOnItsOwn(sandboxStatus, sandboxPhase)
  const visible = live || stopped
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [mountedAt, setMountedAt] = useState<number | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const rootRef = useRef<HTMLDivElement | null>(null)

  // The server's start time survives leaving the chat. The local clock only
  // covers the moments before the server reports one (while starting).
  const reported = sandboxStatus?.startedAt
    ? Date.parse(sandboxStatus.startedAt)
    : Number.NaN
  const startedAt = Number.isFinite(reported) ? reported : mountedAt

  useEffect(() => {
    if (!live) {
      setMountedAt(null)
      return
    }
    setMountedAt(current => current ?? Date.now())
  }, [live])

  useEffect(() => {
    if (visible) return
    setOpen(false)
    setEditing(false)
  }, [visible])

  useEffect(() => {
    if (!visible) return
    const timer = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [visible])

  // Refresh once per open. A new callback identity must not re-fetch.
  const refreshRef = useRef(onRefreshSandbox)
  refreshRef.current = onRefreshSandbox

  useEffect(() => {
    if (!open) {
      setEditing(false)
      return
    }
    void refreshRef.current?.()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    const onPointer = (event: MouseEvent) => {
      if (rootRef.current?.contains(event.target as Node)) return
      setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onPointer)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('mousedown', onPointer)
    }
  }, [open])

  if (!visible) return null

  const transition = sandboxTransitionLabel(sandboxStatus, sandboxPhase)
  const elapsed =
    startedAt == null ? '0s' : formatSandboxElapsed(now - startedAt)
  const specs = sandboxSpecs(sandboxStatus)
  // One short line to glance at. The full rules are in its tooltip.
  const lifecycle = stopped
    ? sandboxStopSummary(sandboxStatus, now)
    : transition
      ? ''
      : sandboxLifecycleSummary(sandboxStatus, now)
  const lifecycleDetail = stopped
    ? sandboxStopLine(sandboxStatus, now)
    : sandboxLifecycleLine(sandboxStatus, now)
  const title = stopped ? 'Sandbox stopped' : '1 Sandbox'

  return (
    <TooltipProvider delayDuration={300}>
      <div
        ref={rootRef}
        className={cn(
          'pointer-events-none absolute inset-x-0 bottom-full z-10 flex flex-col items-start gap-2 pb-2',
          embedded && 'px-4'
        )}
      >
        {open ? (
          <div
            role="dialog"
            aria-label="Sandboxes"
            className="border-border/70 bg-popover text-popover-foreground pointer-events-auto w-full rounded-2xl border p-1.5 shadow-[0_8px_30px_-12px_rgba(0,0,0,0.2)] dark:shadow-[0_12px_32px_-12px_rgba(0,0,0,0.7)]"
          >
            <div className="text-muted-foreground flex items-center justify-between py-0.5 pr-1 pl-2.5 text-[13px]">
              <span>{title}</span>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    aria-label="Minimize"
                    className="hover:bg-muted hover:text-foreground flex size-6 items-center justify-center rounded-md"
                    onClick={() => setOpen(false)}
                  >
                    <Minus className="size-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="top" className="flex items-center gap-2">
                  Minimize
                  <kbd className="bg-muted text-muted-foreground rounded px-1 text-[11px]">
                    Esc
                  </kbd>
                </TooltipContent>
              </Tooltip>
            </div>
            <div className="group/row hover:bg-muted/70 focus-within:bg-muted/70 rounded-lg py-1 pr-1 pl-2.5 text-[13px]">
              <div className="flex min-h-6 items-center gap-2">
                {sandboxStatus?.backend === 'modal' ? (
                  <ModalGlyph
                    className={cn('size-3.5 shrink-0', stopped && 'opacity-50')}
                  />
                ) : (
                  <Container className="text-muted-foreground size-3.5 shrink-0" />
                )}
                <span className="shrink-0">
                  {sandboxBackendName(sandboxStatus)}
                </span>
                {specs ? (
                  <span className="text-muted-foreground min-w-0 truncate">
                    {specs}
                  </span>
                ) : null}
                {stopped ? null : (
                  <span className="text-muted-foreground shrink-0 tabular-nums">
                    {transition ?? elapsed}
                  </span>
                )}
                <span className="flex-1" />
                {onSandboxBackendSelect ? (
                  <button
                    type="button"
                    aria-expanded={editing}
                    className={cn(
                      'text-muted-foreground hover:bg-background hover:text-foreground shrink-0 rounded-md px-2 py-0.5 text-[12px]',
                      editing && 'bg-background text-foreground'
                    )}
                    onClick={() => setEditing(current => !current)}
                  >
                    {editing ? 'Done' : 'Edit'}
                  </button>
                ) : null}
                {stopped && onSandboxStart ? (
                  <button
                    type="button"
                    className="bg-foreground text-background shrink-0 rounded-md px-2 py-0.5 text-[12px] font-medium hover:opacity-90"
                    onClick={() => void onSandboxStart()}
                  >
                    Start
                  </button>
                ) : null}
                {live && onSandboxStop && !transition ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        type="button"
                        aria-label="Stop sandbox"
                        className="text-muted-foreground hover:bg-background hover:text-foreground flex size-6 shrink-0 items-center justify-center rounded-md opacity-0 group-hover/row:opacity-100 focus-visible:opacity-100"
                        onClick={() => void onSandboxStop()}
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent side="top">Stop</TooltipContent>
                  </Tooltip>
                ) : null}
              </div>
              {lifecycle ? (
                <p
                  data-testid="sandbox-lifecycle"
                  title={lifecycleDetail}
                  className="text-muted-foreground w-fit pt-0.5 pr-2 pb-0.5 pl-[22px] text-[12px] leading-snug"
                >
                  {lifecycle}
                </p>
              ) : null}
            </div>
            {editing && onSandboxBackendSelect ? (
              <div className="border-border/60 mt-1.5 border-t">
                <ComposerSandboxPicker
                  embedded
                  variant="edit"
                  sandboxStatus={sandboxStatus}
                  sandboxPhase={sandboxPhase}
                  onRequestClose={() => setEditing(false)}
                  onSandboxBackendSelect={onSandboxBackendSelect}
                  onSandboxComputeChange={onSandboxComputeChange}
                  onSandboxStart={onSandboxStart}
                  onSandboxStop={onSandboxStop}
                  onSandboxRestart={onSandboxRestart}
                  onLoadLocalSystem={onLoadLocalSystem}
                  onRefreshSandbox={onRefreshSandbox}
                />
              </div>
            ) : null}
          </div>
        ) : null}
        <button
          type="button"
          className={cn(
            'border-border/70 bg-popover text-foreground/90 hover:bg-muted pointer-events-auto inline-flex w-fit max-w-full items-center gap-2 rounded-full border px-3 py-1 text-[13px]',
            open && 'bg-muted'
          )}
          aria-label="Sandbox"
          aria-expanded={open}
          onClick={() => setOpen(current => !current)}
        >
          {stopped ? (
            <>
              <span
                className="border-muted-foreground/60 size-2 shrink-0 rounded-full border"
                aria-hidden
              />
              <span>Sandbox stopped</span>
            </>
          ) : (
            <>
              <ActivityDots />
              <span className="text-muted-foreground tabular-nums">1</span>
              <span>Sandbox</span>
            </>
          )}
        </button>
      </div>
    </TooltipProvider>
  )
}
