import type {
  HitlActionRequest,
  HitlDecision,
  HitlDecisionType,
  HitlReviewConfig
} from '@sandwalk/agent-ui-core'
import { ShieldAlert, Terminal } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type HitlDecisionCardProps = {
  actionRequests: HitlActionRequest[]
  reviewConfigs: HitlReviewConfig[]
  onSubmit: (decisions: HitlDecision[]) => void | Promise<void>
  submitting?: boolean
  className?: string
}

function allowedFor(
  action: HitlActionRequest,
  reviewConfigs: HitlReviewConfig[]
): HitlDecisionType[] {
  const match = reviewConfigs.find(cfg => cfg.actionName === action.name)
  const allowed = match?.allowedDecisions?.length
    ? match.allowedDecisions
    : (['approve', 'edit', 'reject'] as HitlDecisionType[])
  return allowed
}

function isSkillsManageBatchable(actionRequests: HitlActionRequest[]) {
  return actionRequests.some(action => {
    if (action.name !== 'skills_manage') return false
    const act = String(action.args?.action || '').toLowerCase()
    return (
      act === 'install' ||
      act === 'add' ||
      act === 'remove' ||
      act === 'uninstall' ||
      act === 'create'
    )
  })
}

function skillsActionLabel(actionRequests: HitlActionRequest[]) {
  const acts = new Set(
    actionRequests.map(action =>
      String(action.args?.action || '').toLowerCase()
    )
  )
  const removing = [...acts].some(act =>
    ['remove', 'uninstall'].includes(act)
  )
  const installing = [...acts].some(act =>
    ['install', 'add', 'create'].includes(act)
  )
  if (removing && installing) return 'Skill changes'
  if (removing) return 'Remove skills'
  if (installing) return 'Install skills'
  return 'skills_manage'
}

function titleFor(actionRequests: HitlActionRequest[]) {
  if (isSkillsManageBatchable(actionRequests)) {
    return skillsActionLabel(actionRequests)
  }
  if (actionRequests.length === 1) {
    return actionRequests[0]?.name || 'tool'
  }
  return `${actionRequests.length} tool calls`
}

export function HitlDecisionCard({
  actionRequests,
  reviewConfigs,
  onSubmit,
  submitting = false,
  className
}: HitlDecisionCardProps) {
  const primary = actionRequests[0]
  const allowed = primary
    ? allowedFor(primary, reviewConfigs)
    : (['approve', 'edit', 'reject'] as HitlDecisionType[])
  const canApprove = allowed.includes('approve')
  const canReject = allowed.includes('reject')
  const canEdit = allowed.includes('edit') && actionRequests.length === 1
  const count = actionRequests.length
  const batch = count > 1
  const skillsBatch = isSkillsManageBatchable(actionRequests)
  const approveLabel = skillsBatch
    ? 'Approve'
    : batch
      ? `Approve all (${count})`
      : 'Approve'
  const rejectLabel = batch ? `Reject all (${count})` : 'Reject'

  const [editing, setEditing] = useState(false)
  const [argsText, setArgsText] = useState(() =>
    JSON.stringify(primary?.args ?? {}, null, 2)
  )
  const [argsError, setArgsError] = useState<string | null>(null)

  const submitApprove = () => {
    if (submitting || actionRequests.length === 0) return
    // Skill install/remove: one approve covers the rest of this run's batch.
    void onSubmit(
      actionRequests.map(() =>
        skillsBatch
          ? { type: 'approve', scope: 'remaining' }
          : { type: 'approve' }
      )
    )
  }

  const submitReject = () => {
    if (submitting || actionRequests.length === 0) return
    void onSubmit(
      actionRequests.map(() => ({
        type: 'reject',
        message:
          'User rejected this action. Do not retry the same tool call unless the user explicitly asks.'
      }))
    )
  }

  const submitEdit = () => {
    if (!primary || submitting) return
    try {
      const parsed = JSON.parse(argsText || '{}') as unknown
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        setArgsError('Args must be a JSON object.')
        return
      }
      setArgsError(null)
      void onSubmit([
        {
          type: 'edit',
          editedAction: {
            name: primary.name,
            args: parsed as Record<string, unknown>
          }
        }
      ])
    } catch {
      setArgsError('Invalid JSON.')
    }
  }

  return (
    <div
      className={cn(
        'border-border/70 bg-muted/25 mx-auto w-full max-w-[44rem] rounded-md border px-2 py-1.5',
        className
      )}
    >
      <div className="flex items-start justify-between gap-2 py-0.5">
        <span className="flex min-w-0 items-start gap-2">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
          <span className="min-w-0">
            <span className="text-foreground block truncate text-sm font-medium leading-none">
              Pending approval
            </span>
            <span className="text-muted-foreground/80 mt-0.5 flex min-w-0 items-center gap-1 text-xs">
              <Terminal className="h-3 w-3 shrink-0" />
              <span className="truncate font-mono">{titleFor(actionRequests)}</span>
            </span>
          </span>
        </span>
      </div>

      <div className="space-y-1.5 pb-1 pt-1">
        {skillsBatch ? (
          <p className="text-muted-foreground text-[11px]">
            Approving allows all skill install/remove calls for the rest of
            this run (including batch loops).
          </p>
        ) : null}

        {actionRequests.map((action, index) => (
          <div key={`${action.name}-${index}`} className="space-y-1">
            {actionRequests.length > 1 ? (
              <p className="text-muted-foreground font-mono text-[11px]">
                {index + 1}/{actionRequests.length} · {action.name}
              </p>
            ) : null}
            <pre className="border-border/40 bg-background/60 text-muted-foreground max-h-36 overflow-auto whitespace-pre-wrap rounded-sm border px-2 py-1.5 font-mono text-xs">
              {JSON.stringify(action.args ?? {}, null, 2)}
            </pre>
          </div>
        ))}

        {editing && canEdit ? (
          <div className="space-y-1">
            <textarea
              value={argsText}
              disabled={submitting}
              onChange={event => {
                setArgsText(event.target.value)
                setArgsError(null)
              }}
              rows={5}
              className="border-border/40 bg-background/60 text-muted-foreground w-full rounded-sm border px-2 py-1.5 font-mono text-xs"
            />
            {argsError ? (
              <p className="text-destructive text-[11px]">{argsError}</p>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="flex items-center justify-between gap-2 pb-0.5 pt-0.5">
        <div className="flex items-center gap-1">
          {canEdit ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={submitting}
              className="h-7 px-2 text-xs"
              aria-label={editing ? 'Cancel edit args' : 'Edit args'}
              onClick={() => {
                setEditing(current => !current)
                setArgsError(null)
              }}
            >
              {editing ? 'Cancel' : 'Edit'}
            </Button>
          ) : (
            <span />
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {editing && canEdit ? (
            <Button
              type="button"
              size="sm"
              disabled={submitting}
              className="h-7 px-2.5 text-xs"
              aria-label="Apply edit"
              onClick={submitEdit}
            >
              {submitting ? 'Applying…' : 'Apply'}
            </Button>
          ) : (
            <>
              {canReject ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={submitting}
                  className="h-7 px-2.5 text-xs"
                  aria-label={rejectLabel}
                  onClick={submitReject}
                >
                  {rejectLabel}
                </Button>
              ) : null}
              {canApprove ? (
                <Button
                  type="button"
                  size="sm"
                  disabled={submitting}
                  className="h-7 px-2.5 text-xs"
                  aria-label={approveLabel}
                  onClick={submitApprove}
                >
                  {submitting ? 'Submitting…' : approveLabel}
                </Button>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
