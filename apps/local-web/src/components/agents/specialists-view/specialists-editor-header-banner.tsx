import { AlertTriangle, ArrowLeft, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { DetailStickyNav } from '@/components/agents/detail-sticky-nav'
import { SpecialistToggle } from '@/components/agents/specialists-view/specialists-view-shared'
import { Button } from '@/components/ui/button'

import type { SpecialistsEditorState } from './use-specialists-editor'

export function SpecialistsEditorHeader({
  mode,
  specialistId,
  state,
  onBack
}: {
  mode: 'new' | 'edit'
  specialistId: string | null
  state: SpecialistsEditorState
  onBack: () => void
}) {
  const navigate = useNavigate()
  const { form, togglePendingId, deleting, saving, toggleSpecialistEnabled, remove } =
    state

  return (
    <DetailStickyNav>
      <div className="flex items-center gap-2 text-sm">
        <button
          type="button"
          onClick={onBack}
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </button>
        <span className="text-muted-foreground/40">/</span>
        <button
          type="button"
          onClick={() => navigate('/dashboard/specialists')}
          className="text-muted-foreground hover:text-foreground transition-colors"
        >
          Specialists
        </button>
      </div>
      {mode === 'edit' || mode === 'new' ? (
        <div className="flex flex-wrap items-center justify-end gap-3">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground text-xs">
              {form.enabled ? 'On' : 'Off'}
            </span>
            <SpecialistToggle
              enabled={form.enabled}
              pending={
                mode === 'edit' &&
                Boolean(specialistId) &&
                togglePendingId === specialistId
              }
              label={form.enabled ? 'Disable specialist' : 'Enable specialist'}
              onToggle={() => {
                if (mode !== 'edit' || !specialistId) {
                  state.setForm(current => ({
                    ...current,
                    enabled: !current.enabled
                  }))
                  return
                }
                const next = !form.enabled
                state.setForm(current => ({ ...current, enabled: next }))
                void toggleSpecialistEnabled(specialistId, next)
              }}
            />
          </div>
          {mode === 'edit' ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-red-600 hover:text-red-700"
              disabled={deleting || saving}
              onClick={() => void remove()}
            >
              <Trash2 className="mr-1 size-3.5" />
              Delete
            </Button>
          ) : null}
        </div>
      ) : null}
    </DetailStickyNav>
  )
}

export function SpecialistsEditorCapabilityBanner({
  state
}: {
  state: SpecialistsEditorState
}) {
  if (state.capabilityIssues.length === 0) return null

  return (
    <div className="border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200 flex gap-3 rounded-xl border px-3.5 py-3 text-sm">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0 space-y-1">
        <p className="font-medium text-amber-900 dark:text-amber-100">
          Some required capabilities aren’t ready
        </p>
        <p className="text-amber-800/80 dark:text-amber-200/80 text-xs">
          You can still use this specialist. Missing or disabled skills and MCPs
          won’t be available until you install, connect, or enable them.
        </p>
        <ul className="text-amber-800/90 dark:text-amber-200/90 mt-1 space-y-0.5 text-xs">
          {state.capabilityIssues.map(issue => (
            <li key={`${issue.kind}:${issue.name}`}>
              {issue.kind === 'skill' ? 'Skill' : 'MCP'}{' '}
              <span className="font-medium">{issue.name}</span> — {issue.detail}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
