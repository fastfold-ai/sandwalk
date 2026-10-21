import type {
  AgentCatalogSkillAudit,
  AgentSkill
} from '@sandwalk/agent-ui-core'
import { ArrowLeft, Check, Copy, Loader, MoreHorizontal, Trash2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { auditStatusBadgeClass } from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

export function SkillsBreadcrumb({ onBack }: { onBack: () => void }) {
  const navigate = useNavigate()
  return (
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
        onClick={() => navigate('/dashboard/skills')}
        className="text-muted-foreground hover:text-foreground transition-colors"
      >
        Skills
      </button>
    </div>
  )
}

export function SkillsRemoveDialog({
  removeTarget,
  onOpenChange,
  onConfirm
}: {
  removeTarget:
    | { type: 'single'; name: string }
    | { type: 'filtered'; count: number }
    | null
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
}) {
  return (
    <AlertDialog open={Boolean(removeTarget)} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-sm">
        <AlertDialogHeader>
          <AlertDialogTitle>
            {removeTarget?.type === 'filtered'
              ? 'Remove skills?'
              : 'Remove skill?'}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {removeTarget?.type === 'filtered'
              ? `Remove ${removeTarget.count} skills in the current filter? This cannot be undone.`
              : `Remove “${removeTarget?.name || 'this skill'}”? This uninstalls it from this machine and cannot be undone.`}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={onConfirm}
          >
            Remove
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function SkillsShMetrics({
  source,
  installs,
  audits,
  githubStars,
  firstSeen
}: {
  source: string
  installs: number
  audits: AgentCatalogSkillAudit['audits']
  githubStars?: number | null
  firstSeen?: string | null
}) {
  const compact = new Intl.NumberFormat('en-US', {
    notation: 'compact',
    maximumFractionDigits: 1
  })
  const installLabel = compact.format(installs)
  const starsLabel =
    typeof githubStars === 'number' && githubStars > 0
      ? compact.format(githubStars)
      : null

  return (
    <aside className="space-y-3 lg:sticky lg:top-4">
      <div className="border-border/50 bg-muted/20 rounded-xl border p-3">
        <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
          Installs
        </p>
        <p className="mt-1 text-3xl font-semibold">{installLabel}</p>
      </div>
      <div className="border-border/50 bg-muted/20 rounded-xl border p-3">
        <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
          Repository
        </p>
        <p className="mt-1 break-all text-sm">{source || 'Unknown'}</p>
      </div>
      {starsLabel ? (
        <div className="border-border/50 bg-muted/20 rounded-xl border p-3">
          <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
            GitHub Stars
          </p>
          <p className="mt-1 text-sm font-medium">★ {starsLabel}</p>
        </div>
      ) : null}
      {firstSeen ? (
        <div className="border-border/50 bg-muted/20 rounded-xl border p-3">
          <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
            First Seen
          </p>
          <p className="mt-1 text-sm">{firstSeen}</p>
        </div>
      ) : null}
      <div className="border-border/50 bg-muted/20 rounded-xl border p-3">
        <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
          Security Audits
        </p>
        <div className="mt-2 space-y-2">
          {audits.length === 0 ? (
            <p className="text-muted-foreground text-xs">No audits available.</p>
          ) : (
            audits.map(audit => (
              <div
                key={`${audit.provider}-${audit.slug}`}
                className="flex items-center justify-between gap-2"
              >
                <span className="truncate text-xs">{audit.provider}</span>
                <span
                  className={cn(
                    'rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase',
                    auditStatusBadgeClass(audit.status)
                  )}
                >
                  {audit.status || 'unknown'}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </aside>
  )
}

export function SkillsShMetricsLoading() {
  return (
    <aside className="lg:sticky lg:top-4 lg:pt-1">
      <div className="text-muted-foreground flex items-center gap-2 text-xs">
        <Loader className="size-3.5 shrink-0 animate-spin" aria-hidden />
        <span>Fetching Skills.sh metadata</span>
      </div>
    </aside>
  )
}

export function SkillEnabledToggle({
  skill,
  pending,
  onToggle
}: {
  skill: AgentSkill
  pending: boolean
  onToggle: (name: string, enabled: boolean) => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={skill.enabled}
      aria-label={`${skill.enabled ? 'Disable' : 'Enable'} ${skill.name}`}
      disabled={pending}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        skill.enabled
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700',
        pending && 'cursor-not-allowed opacity-60'
      )}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        onToggle(skill.name, !skill.enabled)
      }}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          skill.enabled ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </button>
  )
}

export function SkillRemoveButton({
  skill,
  pending,
  onRemove
}: {
  skill: AgentSkill
  pending: boolean
  onRemove: (name: string) => void
}) {
  if (skill.source === 'bundled') return null
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-muted-foreground/70 hover:text-muted-foreground h-6 w-6 p-0"
          disabled={pending}
          onClick={event => {
            event.preventDefault()
            event.stopPropagation()
          }}
        >
          <MoreHorizontal className="size-3.5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          className="text-red-600 focus:text-red-700"
          onClick={event => {
            event.preventDefault()
            event.stopPropagation()
            onRemove(skill.name)
          }}
        >
          <Trash2 className="size-3.5" />
          Remove
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function InstallCommandBlock({
  command,
  copied,
  onCopy
}: {
  command: string
  copied: boolean
  onCopy: () => void
}) {
  return (
    <div className="border-border/50 bg-muted/20 overflow-hidden rounded-xl border">
      <div className="border-border/50 bg-muted/25 flex items-center justify-between border-b px-3 py-1.5">
        <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
          bash
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 gap-1.5 px-2 text-xs"
          onClick={onCopy}
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5" />
              Copied!
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              Copy
            </>
          )}
        </Button>
      </div>
      <pre className="text-muted-foreground overflow-x-auto p-3 font-mono text-sm">
        <code>{command}</code>
      </pre>
    </div>
  )
}
