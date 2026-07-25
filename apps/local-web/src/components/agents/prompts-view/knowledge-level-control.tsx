import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { useEffect, useState } from 'react'

import { Slider } from '@/components/ui/slider'

export type KnowledgeLevel = 'low' | 'medium' | 'high'

const LEVELS: KnowledgeLevel[] = ['low', 'medium', 'high']

const LABELS: Record<KnowledgeLevel, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High'
}

function normalizeLevel(value: string | null | undefined): KnowledgeLevel {
  const raw = String(value || '')
    .trim()
    .toLowerCase()
  if (raw === 'low' || raw === 'medium' || raw === 'high') return raw
  return 'high'
}

export function KnowledgeLevelControl({
  connected,
  value,
  saving,
  onChange,
  className
}: {
  connected: boolean
  value: string | null | undefined
  saving?: boolean
  onChange: (level: KnowledgeLevel) => void | Promise<void>
  className?: string
}) {
  const committed = normalizeLevel(value)
  const [draft, setDraft] = useState<KnowledgeLevel | null>(null)
  const display = draft ?? committed
  const index = Math.max(0, LEVELS.indexOf(display))

  useEffect(() => {
    setDraft(null)
  }, [committed])

  const commit = (next: KnowledgeLevel) => {
    setDraft(null)
    if (!connected || next === committed) return
    void onChange(next)
  }

  return (
    <section className={className ?? 'space-y-2'}>
      <div>
        <span className="text-sm font-medium">
          Knowledge Level
          {saving ? (
            <span className="text-muted-foreground ml-2 text-xs font-normal">
              saving…
            </span>
          ) : null}
        </span>
        <p className="text-muted-foreground mt-0.5 text-xs leading-relaxed">
          Higher levels use more input tokens. Prefer High for complex work,
          Medium for everyday tasks, Low for simple ones.
        </p>
      </div>

      <div className="space-y-1.5">
        <Slider
          min={0}
          max={2}
          step={1}
          value={[index]}
          disabled={!connected}
          aria-label="Knowledge level"
          onValueChange={values => {
            const next = LEVELS[values[0] ?? 0] || 'high'
            setDraft(next)
          }}
          onValueCommit={values => {
            const next = LEVELS[values[0] ?? 0] || 'high'
            commit(next)
          }}
        />
        <div className="text-muted-foreground flex justify-between text-[11px]">
          {LEVELS.map(item => (
            <button
              key={item}
              type="button"
              disabled={!connected || Boolean(saving)}
              className={
                item === display
                  ? 'text-foreground font-medium'
                  : 'hover:text-foreground'
              }
              onClick={() => commit(item)}
            >
              {LABELS[item]}
            </button>
          ))}
        </div>
      </div>
    </section>
  )
}

export function knowledgeLevelFromSettings(
  settings: RuntimeSettings | null | undefined
): KnowledgeLevel {
  return normalizeLevel(settings?.knowledgeLevel)
}
