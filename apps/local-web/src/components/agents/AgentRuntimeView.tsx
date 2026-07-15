import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { Check, Loader2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { BusyConfirmOverlay } from '@/components/BusyConfirmOverlay'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

import {
  clampInt,
  settingsToDraft,
  type RuntimeDraft
} from './runtime-view/runtime-view-fields'
import {
  RuntimeLangGraphSection,
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
      description: 'Applying LangGraph and tool-calling limits.'
    })
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
      setOverlay({
        phase: 'done',
        message: 'Runtime saved',
        description: 'New sessions use these limits.'
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
      <div className="mx-auto max-w-3xl space-y-10 px-8 py-10">
        <div>
          <h2 className="text-2xl font-semibold">Runtime</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            LangGraph loop limits, tool calling, traces, and health overrides
            for agent runs.
          </p>
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        <RuntimeLangGraphSection {...sectionProps} />
        <RuntimeToolCallingSection {...sectionProps} />
        <RuntimeToolTracesSection {...sectionProps} />
        <RuntimeTimeoutsSection {...sectionProps} />
        <RuntimeToolHealthSection {...sectionProps} />

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

        <div className="flex justify-end pt-2">
          <Button
            size="sm"
            disabled={!connected || saving || !dirty}
            onClick={() => void save()}
          >
            {saving ? <Loader2 className="animate-spin" /> : <Check />}
            Save
          </Button>
        </div>
      </div>
    </ScrollArea>
  )
}
