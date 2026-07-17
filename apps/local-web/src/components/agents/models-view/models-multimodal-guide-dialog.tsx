import type { AgentModel } from '@sandwalk/agent-ui-core'
import { Check, Search } from 'lucide-react'
import { Fragment, useEffect, useMemo, useState } from 'react'

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { resolveMultimodalCapabilityFlags } from '@/lib/multimodal-attach'
import { cn } from '@/lib/utils'

const PROVIDER_ORDER = [
  'anthropic',
  'openai',
  'google',
  'xai',
  'nvidia',
  'opencode',
  'local'
] as const

const PROVIDER_LABELS: Record<string, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Gemini',
  xai: 'Grok',
  nvidia: 'NVIDIA',
  opencode: 'OpenCode',
  local: 'Local'
}

const MODALITIES = [
  { key: 'supportsImageInputs' as const, id: 'image', label: 'Image' },
  { key: 'supportsPdfInputs' as const, id: 'pdf', label: 'PDF' },
  { key: 'supportsAudioInputs' as const, id: 'audio', label: 'Audio' },
  { key: 'supportsVideoInputs' as const, id: 'video', label: 'Video' }
] as const

type CapabilityFilter = 'all' | (typeof MODALITIES)[number]['id']

function providerKey(model: AgentModel): string {
  if (model.source === 'profile' || model.provider === 'local') return 'local'
  return model.provider
}

function providerLabelFor(key: string) {
  return PROVIDER_LABELS[key] || key
}

function providerSortKey(model: AgentModel): number {
  const key = providerKey(model)
  const idx = PROVIDER_ORDER.indexOf(key as (typeof PROVIDER_ORDER)[number])
  return idx >= 0 ? idx : 50
}

function modelCapabilityFlags(model: AgentModel) {
  return resolveMultimodalCapabilityFlags(model)
}

function supportsCapability(
  model: AgentModel,
  capability: Exclude<CapabilityFilter, 'all'>
): boolean {
  const flags = modelCapabilityFlags(model)
  const mod = MODALITIES.find(item => item.id === capability)
  return mod ? Boolean(flags[mod.key]) : false
}

export function ModelsMultimodalGuideDialog({
  open,
  onOpenChange,
  models
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  models: AgentModel[]
}) {
  const [query, setQuery] = useState('')
  const [capability, setCapability] = useState<CapabilityFilter>('all')

  useEffect(() => {
    if (!open) return
    setQuery('')
    setCapability('all')
  }, [open])

  const allRows = useMemo(() => {
    return [...models]
      .filter(model => model.source !== 'custom')
      .sort((a, b) => {
        const byProvider = providerSortKey(a) - providerSortKey(b)
        if (byProvider !== 0) return byProvider
        return a.label.localeCompare(b.label)
      })
  }, [models])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return allRows.filter(model => {
      if (capability !== 'all' && !supportsCapability(model, capability)) {
        return false
      }
      if (!needle) return true
      const key = providerKey(model)
      return (
        model.label.toLowerCase().includes(needle) ||
        model.id.toLowerCase().includes(needle) ||
        providerLabelFor(key).toLowerCase().includes(needle)
      )
    })
  }, [allRows, capability, query])

  const grouped = useMemo(() => {
    const groups: Array<{ key: string; label: string; models: AgentModel[] }> =
      []
    for (const model of filtered) {
      const key = providerKey(model)
      const last = groups[groups.length - 1]
      if (last?.key === key) {
        last.models.push(model)
      } else {
        groups.push({ key, label: providerLabelFor(key), models: [model] })
      }
    }
    return groups
  }, [filtered])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[min(90dvh,40rem)] gap-3 overflow-y-auto overflow-x-hidden p-5 sm:max-w-md">
        <DialogHeader className="space-y-1">
          <DialogTitle className="text-base">
            Multimodal input support
          </DialogTitle>
          <p className="text-muted-foreground text-xs leading-relaxed">
            Which models accept image, PDF, audio, or video natively. Files
            still upload to the workspace when a model does not.
          </p>
        </DialogHeader>

        <div className="flex gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2" />
            <Input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Search models…"
              className="h-8 pl-8 text-xs"
            />
          </div>
          <select
            value={capability}
            onChange={event =>
              setCapability(event.target.value as CapabilityFilter)
            }
            aria-label="Filter by capability"
            className={cn(
              'border-input bg-background text-foreground h-8 shrink-0 rounded-md border px-2 text-xs',
              'focus-visible:ring-ring focus-visible:ring-1 focus-visible:outline-none'
            )}
          >
            <option value="all">All capabilities</option>
            {MODALITIES.map(mod => (
              <option key={mod.id} value={mod.id}>
                {mod.label}
              </option>
            ))}
          </select>
        </div>

        <div className="border-border/60 overflow-hidden rounded-lg border">
          <table className="w-full table-fixed border-collapse text-xs">
            <colgroup>
              <col />
              <col className="w-12" />
              <col className="w-12" />
              <col className="w-12" />
              <col className="w-12" />
            </colgroup>
            <thead className="bg-muted/50 text-muted-foreground">
              <tr className="border-b">
                <th className="px-2.5 py-1.5 text-left text-[10px] font-medium tracking-wide uppercase">
                  Model
                </th>
                {MODALITIES.map(mod => (
                  <th
                    key={mod.key}
                    className="px-0.5 py-1.5 text-center text-[10px] font-medium tracking-wide uppercase"
                  >
                    {mod.label.slice(0, 3)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {grouped.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="text-muted-foreground px-3 py-8 text-center"
                  >
                    {allRows.length === 0
                      ? 'No models loaded yet.'
                      : 'No models match.'}
                  </td>
                </tr>
              ) : (
                grouped.map(group => (
                  <Fragment key={group.key}>
                    <tr className="bg-muted/25">
                      <td
                        colSpan={5}
                        className="text-muted-foreground px-2.5 py-1 text-[10px] font-medium tracking-wide uppercase"
                      >
                        {group.label}
                      </td>
                    </tr>
                    {group.models.map(model => (
                      <tr
                        key={`${model.provider}:${model.profileId || ''}:${model.id}`}
                        className="border-border/40 border-b last:border-b-0"
                      >
                        <td className="truncate px-2.5 py-1 font-medium">
                          {model.label}
                        </td>
                        {MODALITIES.map(mod => {
                          const ok = Boolean(modelCapabilityFlags(model)[mod.key])
                          return (
                            <td key={mod.key} className="px-0.5 py-1 text-center">
                              {ok ? (
                                <Check
                                  className="text-foreground mx-auto size-3.5"
                                  aria-label={`${mod.label} supported`}
                                />
                              ) : (
                                <span
                                  className="text-muted-foreground/30"
                                  aria-label={`${mod.label} not supported`}
                                >
                                  ·
                                </span>
                              )}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </DialogContent>
    </Dialog>
  )
}
