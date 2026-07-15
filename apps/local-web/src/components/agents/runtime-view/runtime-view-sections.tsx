import { cn } from '@/lib/utils'

import {
  RuntimeNumberField,
  RuntimeToggle,
  type RuntimeDraft
} from './runtime-view-fields'

type SectionProps = {
  draft: RuntimeDraft
  connected: boolean
  saving: boolean
  onDraftChange: (updater: (current: RuntimeDraft) => RuntimeDraft) => void
}

export function RuntimeLangGraphSection({
  draft,
  connected,
  saving,
  onDraftChange
}: SectionProps) {
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-base font-semibold">LangGraph loop</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          Raise these if long fold/download workflows stop early with a
          recursion-limit error.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <RuntimeNumberField
          label="Recursion limit"
          hint="Max model↔tool graph steps (agent.recursion_limit)."
          value={draft.recursionLimit}
          min={25}
          max={2000}
          step={10}
          disabled={!connected || saving}
          onChange={value =>
            onDraftChange(current => ({ ...current, recursionLimit: value }))
          }
        />
        <RuntimeNumberField
          label="Max SDK turns"
          hint="Soft turn budget used when recursion limit is unset."
          value={draft.maxSdkTurns}
          min={1}
          max={500}
          disabled={!connected || saving}
          onChange={value =>
            onDraftChange(current => ({ ...current, maxSdkTurns: value }))
          }
        />
      </div>
    </section>
  )
}

export function RuntimeToolCallingSection({
  draft,
  connected,
  saving,
  onDraftChange
}: SectionProps) {
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-base font-semibold">Tool calling</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          PTC keeps domain tools behind run_python; native exposes each tool
          schema to the model.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {(
          [
            {
              id: 'ptc' as const,
              label: 'PTC',
              detail: 'Programmatic (default)'
            },
            {
              id: 'native' as const,
              label: 'Native',
              detail: 'Per-tool schemas'
            }
          ] as const
        ).map(option => {
          const selected = draft.toolMode === option.id
          return (
            <button
              key={option.id}
              type="button"
              disabled={!connected || saving}
              onClick={() =>
                onDraftChange(current => ({ ...current, toolMode: option.id }))
              }
              className={cn(
                'rounded-lg border px-3 py-2 text-left text-sm transition-colors',
                selected
                  ? 'border-primary bg-muted/40 ring-primary/20 ring-2'
                  : 'border-border hover:bg-muted/40'
              )}
            >
              <div className="font-medium">{option.label}</div>
              <div className="text-muted-foreground text-xs">
                {option.detail}
              </div>
            </button>
          )
        })}
      </div>
      <RuntimeNumberField
        label="Parallel max threads"
        hint="Cap for parallel specialist / fan-out work."
        value={draft.parallelMaxThreads}
        min={1}
        max={20}
        disabled={!connected || saving}
        onChange={value =>
          onDraftChange(current => ({ ...current, parallelMaxThreads: value }))
        }
      />
    </section>
  )
}

export function RuntimeToolTracesSection({
  draft,
  connected,
  saving,
  onDraftChange
}: SectionProps) {
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-base font-semibold">Tool traces</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          Control how consecutive tool calls collapse in the transcript.
        </p>
      </div>
      <div className="flex items-center justify-between gap-4 rounded-lg border px-3 py-3">
        <div className="min-w-0">
          <div className="text-sm font-medium">Group tool traces</div>
          <p className="text-muted-foreground text-xs">
            Collapse older calls; keep the latest ones detailed.
          </p>
        </div>
        <RuntimeToggle
          enabled={draft.groupToolTraces}
          disabled={!connected || saving}
          label="Group tool traces"
          onToggle={() =>
            onDraftChange(current => ({
              ...current,
              groupToolTraces: !current.groupToolTraces
            }))
          }
        />
      </div>
      <RuntimeNumberField
        label="Trace detail limit"
        hint="How many recent tool calls keep full args/output."
        value={draft.toolTraceDetailLimit}
        min={1}
        max={50}
        disabled={!connected || saving || !draft.groupToolTraces}
        onChange={value =>
          onDraftChange(current => ({
            ...current,
            toolTraceDetailLimit: value
          }))
        }
      />
    </section>
  )
}

export function RuntimeTimeoutsSection({
  draft,
  connected,
  saving,
  onDraftChange
}: SectionProps) {
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-base font-semibold">Timeouts</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          Background watches and interrupt drain windows for long-running work.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <RuntimeNumberField
          label="Background watch (seconds)"
          hint="Max wait for background job watches."
          value={draft.backgroundWatchTimeoutS}
          min={60}
          max={86400}
          step={60}
          disabled={!connected || saving}
          onChange={value =>
            onDraftChange(current => ({
              ...current,
              backgroundWatchTimeoutS: value
            }))
          }
        />
        <RuntimeNumberField
          label="Interrupt drain (seconds)"
          hint="Time allowed to finish in-flight work after stop."
          value={draft.interruptDrainTimeoutS}
          min={1}
          max={120}
          disabled={!connected || saving}
          onChange={value =>
            onDraftChange(current => ({
              ...current,
              interruptDrainTimeoutS: value
            }))
          }
        />
      </div>
    </section>
  )
}

export function RuntimeToolHealthSection({
  draft,
  connected,
  saving,
  onDraftChange
}: SectionProps) {
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-base font-semibold">Tool health</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          Temporarily suppress tools that fail repeatedly during a session.
        </p>
      </div>
      <div className="flex items-center justify-between gap-4 rounded-lg border px-3 py-3">
        <div className="min-w-0">
          <div className="text-sm font-medium">Enable tool health</div>
          <p className="text-muted-foreground text-xs">
            Auto-suppress flaky tools after repeated failures.
          </p>
        </div>
        <RuntimeToggle
          enabled={draft.toolHealthEnabled}
          disabled={!connected || saving}
          label="Enable tool health"
          onToggle={() =>
            onDraftChange(current => ({
              ...current,
              toolHealthEnabled: !current.toolHealthEnabled
            }))
          }
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <RuntimeNumberField
          label="Fail threshold"
          hint="Failures before a tool is suppressed."
          value={draft.toolHealthFailThreshold}
          min={1}
          max={20}
          disabled={!connected || saving || !draft.toolHealthEnabled}
          onChange={value =>
            onDraftChange(current => ({
              ...current,
              toolHealthFailThreshold: value
            }))
          }
        />
        <RuntimeNumberField
          label="Suppress for (seconds)"
          hint="How long a suppressed tool stays unavailable."
          value={draft.toolHealthSuppressSeconds}
          min={30}
          max={86400}
          step={30}
          disabled={!connected || saving || !draft.toolHealthEnabled}
          onChange={value =>
            onDraftChange(current => ({
              ...current,
              toolHealthSuppressSeconds: value
            }))
          }
        />
      </div>
    </section>
  )
}
