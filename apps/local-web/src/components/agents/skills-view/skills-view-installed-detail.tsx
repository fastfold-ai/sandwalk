import type {
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail,
  AgentSkillDetail
} from '@sandwalk/agent-ui-core'
import {
  ArrowUp,
  Box,
  CalendarDays,
  GitBranch,
  Loader2,
  Tag,
  Trash2,
  UserRound
} from 'lucide-react'

import { DetailStickyNav } from '@/components/agents/detail-sticky-nav'
import { MarkdownContent } from '@/components/agents/MarkdownContent'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { catalogCoordsFromInstalledSkill, skillsShSkillUrl, stripFrontmatter } from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

import {
  InstallCommandBlock,
  SkillEnabledToggle,
  SkillsBreadcrumb,
  SkillsRemoveDialog,
  SkillsShMetrics,
  SkillsShMetricsLoading
} from './skills-view-shared'

export function SkillsInstalledDetailView({
  detail,
  catalogSearchEnabled,
  localCatalogDetail,
  localCatalogAudit,
  localCatalogLoading,
  detailInstallCommand,
  detailGithubUrl,
  detailAuthorUrl,
  detailIconSource,
  detailIconInvert,
  detailVersionLabel,
  detailUpdatedLabel,
  updateAvailable = false,
  latestVersionLabel = null,
  copiedInstall,
  pendingEnabled,
  pendingRemove,
  pendingUpgrade,
  batchBusy,
  batchToast,
  removeTarget,
  onBack,
  onCopyInstall,
  onUpgrade,
  onRemove,
  onRemoveDialogOpenChange,
  onConfirmRemove,
  onToggleEnabled
}: {
  detail: AgentSkillDetail
  catalogSearchEnabled: boolean
  localCatalogDetail: AgentCatalogSkillDetail | null
  localCatalogAudit: AgentCatalogSkillAudit | null
  localCatalogLoading: boolean
  detailInstallCommand: string
  detailGithubUrl: string | null
  detailAuthorUrl: string | null
  detailIconSource: string | null
  detailIconInvert: boolean
  detailVersionLabel: string
  detailUpdatedLabel: string
  updateAvailable?: boolean
  latestVersionLabel?: string | null
  copiedInstall: boolean
  pendingEnabled: Record<string, boolean>
  pendingRemove: Record<string, boolean>
  pendingUpgrade: boolean
  batchBusy: boolean
  batchToast: { message: string; tone: 'success' | 'warning' } | null
  removeTarget:
    | { type: 'single'; name: string }
    | { type: 'filtered'; count: number }
    | null
  onBack: () => void
  onCopyInstall: () => void
  onUpgrade: () => void
  onRemove: (name: string) => void
  onRemoveDialogOpenChange: (open: boolean) => void
  onConfirmRemove: () => void
  onToggleEnabled: (name: string, enabled: boolean) => void
}) {
  const localCatalogSource = String(
    localCatalogDetail?.source ||
      catalogCoordsFromInstalledSkill(detail)?.source ||
      ''
  ).trim()
  const localCatalogInstalls = Number(localCatalogDetail?.installs || 0)
  const localCatalogAudits = localCatalogAudit?.audits || []
  const localCatalogCoords = catalogCoordsFromInstalledSkill(detail)
  const showLocalCatalogColumn =
    catalogSearchEnabled &&
    Boolean(localCatalogCoords) &&
    (localCatalogLoading || localCatalogDetail != null)
  const localSkillsShUrl =
    !localCatalogLoading && localCatalogSource
      ? skillsShSkillUrl(localCatalogSource, detail.name)
      : null

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <DetailStickyNav>
        <SkillsBreadcrumb onBack={onBack} />
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button
            type="button"
            variant={updateAvailable ? 'default' : 'ghost'}
            size="sm"
            className={cn(
              'h-7 px-2 text-xs',
              updateAvailable && 'bg-foreground text-background hover:bg-foreground/90'
            )}
            disabled={pendingUpgrade || batchBusy}
            title={
              updateAvailable
                ? latestVersionLabel
                  ? `Upgrade to ${latestVersionLabel}`
                  : 'A newer version is available — run upgrade'
                : 'Sync installed skills to the latest release (sandwalk skills upgrade)'
            }
            onClick={onUpgrade}
          >
            {pendingUpgrade ? (
              <Loader2 className="mr-1 size-3.5 animate-spin" />
            ) : (
              <ArrowUp className="mr-1 size-3.5" />
            )}
            {updateAvailable
              ? latestVersionLabel
                ? `Upgrade to ${latestVersionLabel}`
                : 'Upgrade available'
              : 'Upgrade'}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs text-red-600 hover:text-red-700"
            disabled={Boolean(pendingRemove[detail.name]) || batchBusy}
            onClick={() => onRemove(detail.name)}
          >
            <Trash2 className="mr-1 size-3.5" />
            Remove
          </Button>
          {localSkillsShUrl ? (
            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" asChild>
              <a href={localSkillsShUrl} target="_blank" rel="noreferrer">
                <img
                  src="/suggestions/skills-sh.png"
                  alt=""
                  className="mr-1 size-3.5 rounded object-contain dark:invert"
                />
                View in Skills.sh
              </a>
            </Button>
          ) : null}
          {detailGithubUrl ? (
            <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" asChild>
              <a href={detailGithubUrl} target="_blank" rel="noreferrer">
                <GitBranch className="mr-1 h-3.5 w-3.5" />
                View in GitHub
              </a>
            </Button>
          ) : (
            <span className="text-muted-foreground inline-flex h-7 items-center gap-1.5 px-2 text-xs">
              <GitBranch className="h-3.5 w-3.5" />
              Source not on GitHub
            </span>
          )}
        </div>
      </DetailStickyNav>
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 pt-2 pb-4 md:px-6 md:pt-3 md:pb-6">
          <div
            className={cn(
              'grid items-start gap-4',
              showLocalCatalogColumn
                ? 'lg:grid-cols-[240px_minmax(0,1fr)_220px]'
                : 'lg:grid-cols-[240px_minmax(0,1fr)]'
            )}
          >
            <aside className="space-y-3 lg:sticky lg:top-4 lg:border-r lg:border-border/60 lg:pr-4">
              <div className="space-y-2">
                {detailIconSource ? (
                  <img
                    src={detailIconSource}
                    alt=""
                    className={cn(
                      'size-9 rounded object-contain',
                      detailIconInvert && 'dark:invert'
                    )}
                  />
                ) : (
                  <span className="bg-muted/30 text-muted-foreground grid size-9 shrink-0 place-items-center rounded">
                    <Box className="size-5" />
                  </span>
                )}
                <div className="min-w-0 space-y-0.5">
                  <div className="flex items-start justify-between gap-2">
                    <h1 className="break-all text-lg font-semibold">
                      /{detail.name}
                    </h1>
                    <div className="shrink-0 pt-0.5">
                      <SkillEnabledToggle
                        skill={detail}
                        pending={Boolean(pendingEnabled[detail.name])}
                        onToggle={onToggleEnabled}
                      />
                    </div>
                  </div>
                  <p className="text-muted-foreground mb-6 pb-3 text-sm">
                    {detail.description || 'Runtime skill'}
                  </p>
                  <div className="mt-6 space-y-1 border-t border-border/60 pt-5 text-xs">
                    <div className="text-muted-foreground flex items-center gap-1.5">
                      <Tag className="h-3.5 w-3.5 shrink-0" />
                      <span className="text-foreground/90 font-medium">
                        Version:
                      </span>
                      <span className="truncate">{detailVersionLabel}</span>
                    </div>
                    <div className="text-muted-foreground flex items-center gap-1.5">
                      <CalendarDays className="h-3.5 w-3.5 shrink-0" />
                      <span className="text-foreground/90 font-medium">
                        Last updated:
                      </span>
                      <span className="truncate" title={detailUpdatedLabel}>
                        {detailUpdatedLabel}
                      </span>
                    </div>
                    <div className="text-muted-foreground flex items-center gap-1.5">
                      <UserRound className="h-3.5 w-3.5 shrink-0" />
                      <span className="text-foreground/90 font-medium">
                        Author:
                      </span>
                      {detailAuthorUrl ? (
                        <a
                          href={detailAuthorUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="truncate underline-offset-2 hover:underline"
                        >
                          {detail.author || 'fastfold-ai'}
                        </a>
                      ) : (
                        <span className="truncate">{detail.author || 'unknown'}</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </aside>

            <section className="min-w-0 overflow-x-hidden p-1">
              <div className="mb-4 space-y-1.5">
                <p className="text-muted-foreground text-sm font-medium">
                  Install this skill
                </p>
                <InstallCommandBlock
                  command={detailInstallCommand}
                  copied={copiedInstall}
                  onCopy={onCopyInstall}
                />
              </div>

              <MarkdownContent
                content={stripFrontmatter(detail.content)}
                className="max-w-none text-sm [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_code]:break-words [&_table]:block [&_table]:max-w-full [&_table]:overflow-x-auto"
              />
            </section>

            {localCatalogLoading ? (
              <SkillsShMetricsLoading />
            ) : localCatalogDetail != null ? (
              <SkillsShMetrics
                source={localCatalogSource}
                installs={localCatalogInstalls}
                audits={localCatalogAudits}
                githubStars={localCatalogDetail?.githubStars}
                firstSeen={localCatalogDetail?.firstSeen}
              />
            ) : null}
          </div>
        </div>
      </ScrollArea>
      {batchToast ? (
        <div
          className={cn(
            'fixed bottom-4 right-4 z-50 max-w-xs rounded-md border px-3 py-2 text-xs shadow-md',
            batchToast.tone === 'warning'
              ? 'border-amber-300/70 bg-amber-50 text-amber-900 dark:border-amber-500/40 dark:bg-amber-950/40 dark:text-amber-100'
              : 'border-border/70 bg-background/95 text-foreground'
          )}
          role="status"
          aria-live="polite"
        >
          {batchToast.message}
        </div>
      ) : null}
      <SkillsRemoveDialog
        removeTarget={removeTarget}
        onOpenChange={onRemoveDialogOpenChange}
        onConfirm={onConfirmRemove}
      />
    </div>
  )
}

export { resolveInstalledDetailPresentation } from './skills-view-installed-detail-presentation'
