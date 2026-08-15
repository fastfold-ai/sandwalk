import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { Check, Loader } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { BusyConfirmOverlay } from '@/components/BusyConfirmOverlay'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

import {
  clampInt,
  type RuntimeDraft,
  settingsToDraft} from './runtime-view/runtime-view-fields'
import {
  RuntimeTimeoutsSection,
  RuntimeToolCallingSection,
  RuntimeToolHealthSection,
  RuntimeToolTracesSection
} from './runtime-view/runtime-view-sections'

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
  const [draft, setDraft] = useState<RuntimeDraft>(() =>
    settingsToDraft(runtimeSettings)
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [overlay, setOverlay] = useState<{
    phase: 'working' | 'done'
    message: string
    description?: string
  } | null>(null)

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
    setOverlay({
      phase: 'working',
      message: 'Saving runtime…',
      description: 'Applying tool-calling and timeout settings.'
    })
    try {
      // Recursion limit is fixed high in the agent runtime (LangGraph requires a
      // finite cap; no documented maximum). Do not expose or overwrite it here.
      const next = await onUpdateRuntimeSettings({
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
      setOverlay({
        phase: 'done',
        message: 'Runtime saved',
        description: 'New sessions use these settings.'
      })
      await new Promise(resolve => setTimeout(resolve, 900))
      setOverlay(null)
    } catch (err) {
      setOverlay(null)
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  const sectionProps = {
    draft,
    connected,
    saving,
    onDraftChange: (updater: (current: RuntimeDraft) => RuntimeDraft) =>
      setDraft(updater)
  }

  return (
    <ScrollArea className="flex-1">
      <BusyConfirmOverlay
        open={Boolean(overlay)}
        phase={overlay?.phase || 'working'}
        message={overlay?.message || ''}
        description={overlay?.description}
      />
      <div className="mx-auto w-full max-w-7xl space-y-10 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
        <div>
          <h2 className="text-2xl font-semibold">Runtime</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Tool calling, traces, timeouts, and health overrides for agent runs.
          </p>
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        <RuntimeToolCallingSection {...sectionProps} />
        <RuntimeToolTracesSection {...sectionProps} />
        <RuntimeTimeoutsSection {...sectionProps} />
        <RuntimeToolHealthSection {...sectionProps} />

        <p className="text-muted-foreground text-xs">
          CLI equivalents use{' '}
          <code className="bg-muted rounded px-1 py-0.5 font-mono">
            sandwalk config set agent.&lt;key&gt; &lt;value&gt;
          </code>
          .
        </p>

        <div className="flex justify-end pt-2">
          <Button
            size="sm"
            disabled={!connected || saving || !dirty}
            onClick={() => void save()}
          >
            {saving ? <Loader className="animate-spin" /> : <Check />}
            Save
          </Button>
        </div>
      </div>
    </ScrollArea>
  )
}
