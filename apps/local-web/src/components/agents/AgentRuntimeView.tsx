import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { Check, Loader2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type Draft = {
  recursionLimit: string
  maxSdkTurns: string
  toolMode: 'ptc' | 'native'
  groupToolTraces: boolean
  toolTraceDetailLimit: string
  backgroundWatchTimeoutS: string
  interruptDrainTimeoutS: string
  parallelMaxThreads: string
  toolHealthEnabled: boolean
  toolHealthFailThreshold: string
  toolHealthSuppressSeconds: string
}

function settingsToDraft(settings: RuntimeSettings | null): Draft {
  return {
    recursionLimit: String(settings?.recursionLimit ?? 120),
    maxSdkTurns: String(settings?.maxSdkTurns ?? 30),
    toolMode: settings?.toolMode === 'native' ? 'native' : 'ptc',
    groupToolTraces: settings?.groupToolTraces ?? true,
    toolTraceDetailLimit: String(settings?.toolTraceDetailLimit ?? 1),
    backgroundWatchTimeoutS: String(settings?.backgroundWatchTimeoutS ?? 7200),
    interruptDrainTimeoutS: String(settings?.interruptDrainTimeoutS ?? 10),
    parallelMaxThreads: String(settings?.parallelMaxThreads ?? 5),
    toolHealthEnabled: settings?.toolHealthEnabled ?? true,
    toolHealthFailThreshold: String(settings?.toolHealthFailThreshold ?? 2),
    toolHealthSuppressSeconds: String(
      settings?.toolHealthSuppressSeconds ?? 900
    )
  }
}

function clampInt(
  value: string,
  minimum: number,
  maximum: number,
  fallback: number
) {
  const n = Math.round(Number(value))
  if (!Number.isFinite(n)) return fallback
  return Math.max(minimum, Math.min(maximum, n))
}

function Toggle({
  enabled,
  disabled,
  label,
  onToggle
}: {
  enabled: boolean
  disabled?: boolean
  label: string
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      disabled={disabled}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        enabled
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700',
        disabled && 'cursor-not-allowed opacity-60'
      )}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onToggle()
      }}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          enabled ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </button>
  )
}

function NumberField({
  label,
  hint,
  value,
  min,
  max,
  step,
  disabled,
  onChange
}: {
  label: string
  hint?: string
  value: string
  min: number
  max: number
  step?: number
  disabled?: boolean
  onChange: (value: string) => void
}) {
  return (
    <label className="space-y-1.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <Input
        type="number"
        min={min}
        max={max}
        step={step ?? 1}
        className="w-40"
        value={value}
        disabled={disabled}
        onChange={event => onChange(event.target.value)}
      />
      {hint ? (
        <p className="text-muted-foreground text-xs leading-relaxed">{hint}</p>
      ) : null}
    </label>
  )
}

export function AgentRuntimeView({
  connected,
  runtimeSettings,
  onUpdateRuntimeSettings
}: {
  connected: boolean
  runtimeSettings: RuntimeSettings | null
  onUpdateRuntimeSettings: (
    changes: Partial<RuntimeSettings>
  ) => Promise<RuntimeSettings>
}) {
  const [draft, setDraft] = useState<Draft>(() =>
    settingsToDraft(runtimeSettings)
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setDraft(settingsToDraft(runtimeSettings))
  }, [runtimeSettings])

  const dirty = useMemo(() => {
    if (!runtimeSettings) return true
    const baseline = settingsToDraft(runtimeSettings)
    return JSON.stringify(draft) !== JSON.stringify(baseline)
  }, [draft, runtimeSettings])

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      const next = await onUpdateRuntimeSettings({
        recursionLimit: clampInt(draft.recursionLimit, 25, 2000, 120),
        maxSdkTurns: clampInt(draft.maxSdkTurns, 1, 500, 30),
        toolMode: draft.toolMode,
        groupToolTraces: draft.groupToolTraces,
        toolTraceDetailLimit: clampInt(draft.toolTraceDetailLimit, 1, 50, 1),
        backgroundWatchTimeoutS: clampInt(
          draft.backgroundWatchTimeoutS,
          60,
          86400,
          7200
        ),
        interruptDrainTimeoutS: clampInt(
          draft.interruptDrainTimeoutS,
          1,
          120,
          10
        ),
        parallelMaxThreads: clampInt(draft.parallelMaxThreads, 1, 20, 5),
        toolHealthEnabled: draft.toolHealthEnabled,
        toolHealthFailThreshold: clampInt(
          draft.toolHealthFailThreshold,
          1,
          20,
          2
        ),
        toolHealthSuppressSeconds: clampInt(
          draft.toolHealthSuppressSeconds,
          30,
          86400,
          900
        )
      })
      setDraft(settingsToDraft(next))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto max-w-3xl space-y-10 px-8 py-10">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold">Runtime</h2>
            <p className="text-muted-foreground mt-2 text-sm">
              LangGraph loop limits, tool calling, traces, and health overrides
              for agent runs.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            disabled={!connected || saving || !dirty}
            onClick={() => void save()}
          >
            {saving ? <Loader2 className="animate-spin" /> : <Check />}
            Save
          </Button>
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        <section className="space-y-4">
          <div>
            <h3 className="text-base font-semibold">LangGraph loop</h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Raise these if long fold/download workflows stop early with a
              recursion-limit error.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              label="Recursion limit"
              hint="Max model↔tool graph steps (agent.recursion_limit)."
              value={draft.recursionLimit}
              min={25}
              max={2000}
              step={10}
              disabled={!connected || saving}
              onChange={value =>
                setDraft(current => ({ ...current, recursionLimit: value }))
              }
            />
            <NumberField
              label="Max SDK turns"
              hint="Soft turn budget used when recursion limit is unset."
              value={draft.maxSdkTurns}
              min={1}
              max={500}
              disabled={!connected || saving}
              onChange={value =>
                setDraft(current => ({ ...current, maxSdkTurns: value }))
              }
            />
          </div>
        </section>

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
                    setDraft(current => ({ ...current, toolMode: option.id }))
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
          <NumberField
            label="Parallel max threads"
            hint="Cap for parallel specialist / fan-out work."
            value={draft.parallelMaxThreads}
            min={1}
            max={20}
            disabled={!connected || saving}
            onChange={value =>
              setDraft(current => ({ ...current, parallelMaxThreads: value }))
            }
          />
        </section>

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
            <Toggle
              enabled={draft.groupToolTraces}
              disabled={!connected || saving}
              label="Group tool traces"
              onToggle={() =>
                setDraft(current => ({
                  ...current,
                  groupToolTraces: !current.groupToolTraces
                }))
              }
            />
          </div>
          <NumberField
            label="Trace detail limit"
            hint="How many recent tool calls keep full args/output."
            value={draft.toolTraceDetailLimit}
            min={1}
            max={50}
            disabled={!connected || saving || !draft.groupToolTraces}
            onChange={value =>
              setDraft(current => ({
                ...current,
                toolTraceDetailLimit: value
              }))
            }
          />
        </section>

        <section className="space-y-4">
          <div>
            <h3 className="text-base font-semibold">Timeouts</h3>
            <p className="text-muted-foreground mt-1 text-sm">
              Background watches and interrupt drain windows for long-running
              work.
            </p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              label="Background watch (seconds)"
              hint="Max wait for background job watches."
              value={draft.backgroundWatchTimeoutS}
              min={60}
              max={86400}
              step={60}
              disabled={!connected || saving}
              onChange={value =>
                setDraft(current => ({
                  ...current,
                  backgroundWatchTimeoutS: value
                }))
              }
            />
            <NumberField
              label="Interrupt drain (seconds)"
              hint="Time allowed to finish in-flight work after stop."
              value={draft.interruptDrainTimeoutS}
              min={1}
              max={120}
              disabled={!connected || saving}
              onChange={value =>
                setDraft(current => ({
                  ...current,
                  interruptDrainTimeoutS: value
                }))
              }
            />
          </div>
        </section>

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
            <Toggle
              enabled={draft.toolHealthEnabled}
              disabled={!connected || saving}
              label="Enable tool health"
              onToggle={() =>
                setDraft(current => ({
                  ...current,
                  toolHealthEnabled: !current.toolHealthEnabled
                }))
              }
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField
              label="Fail threshold"
              hint="Failures before a tool is suppressed."
              value={draft.toolHealthFailThreshold}
              min={1}
              max={20}
              disabled={!connected || saving || !draft.toolHealthEnabled}
              onChange={value =>
                setDraft(current => ({
                  ...current,
                  toolHealthFailThreshold: value
                }))
              }
            />
            <NumberField
              label="Suppress for (seconds)"
              hint="How long a suppressed tool stays unavailable."
              value={draft.toolHealthSuppressSeconds}
              min={30}
              max={86400}
              step={30}
              disabled={!connected || saving || !draft.toolHealthEnabled}
              onChange={value =>
                setDraft(current => ({
                  ...current,
                  toolHealthSuppressSeconds: value
                }))
              }
            />
          </div>
        </section>

        <p className="text-muted-foreground text-xs">
          CLI equivalents use{' '}
          <code className="bg-muted rounded px-1 py-0.5 font-mono">
            sandwalk config set agent.&lt;key&gt; &lt;value&gt;
          </code>
          , e.g.{' '}
          <code className="bg-muted rounded px-1 py-0.5 font-mono">
            sandwalk config set agent.recursion_limit{' '}
            {draft.recursionLimit || 120}
          </code>
          .
        </p>
      </div>
    </ScrollArea>
  )
}
