import type {
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail,
  AgentSkillDetail
} from '@sandwalk/agent-ui-core'
import {
  ArrowLeft,
  Box,
  CalendarDays,
  GitBranch,
  Tag,
  Trash2,
  UserRound
} from 'lucide-react'

import { MarkdownContent } from '@/components/agents/MarkdownContent'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  featuredSkillIcon,
  isFeaturedSkill,
  skillIcon,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import {
  catalogCoordsFromInstalledSkill,
  displaySkillVersion,
  formatSkillUpdatedLabel,
  skillAuthorUrl,
  skillGithubUrl,
  skillsShSkillUrl,
  stripFrontmatter
} from '@/lib/skills-catalog'
import { cn } from '@/lib/utils'

import {
  InstallCommandBlock,
  SkillEnabledToggle,
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
  copiedInstall,
  pendingEnabled,
  pendingRemove,
  batchBusy,
  removeTarget,
  onBack,
  onCopyInstall,
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
  copiedInstall: boolean
  pendingEnabled: Record<string, boolean>
  pendingRemove: Record<string, boolean>
  batchBusy: boolean
  removeTarget:
    | { type: 'single'; name: string }
    | { type: 'filtered'; count: number }
    | null
  onBack: () => void
  onCopyInstall: () => void
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
    <>
      <ScrollArea className="flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 md:p-6">
          <div className="flex items-center justify-between">
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
                onClick={onBack}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                Skills
              </button>
            </div>
            <div className="flex items-center gap-2">
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
                <a
                  href={localSkillsShUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-md border border-border/70 px-3 py-1.5 text-xs hover:bg-muted"
                >
                  <img
                    src="/suggestions/skills-sh.png"
                    alt=""
                    className="size-3.5 rounded object-contain dark:invert"
                  />
                  View in Skills.sh
                </a>
              ) : null}
              {detailGithubUrl ? (
                <a
                  href={detailGithubUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-md border border-border/70 px-3 py-1.5 text-xs hover:bg-muted"
                >
                  <GitBranch className="h-3.5 w-3.5" />
                  View in GitHub
                </a>
              ) : (
                <span className="text-muted-foreground inline-flex items-center gap-1.5 rounded-md border border-border/60 px-3 py-1.5 text-xs">
                  <GitBranch className="h-3.5 w-3.5" />
                  Source not on GitHub
                </span>
              )}
            </div>
          </div>

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
              />
            ) : null}
          </div>
        </div>
      </ScrollArea>
      <SkillsRemoveDialog
        removeTarget={removeTarget}
        onOpenChange={onRemoveDialogOpenChange}
        onConfirm={onConfirmRemove}
      />
    </>
  )
}

export function resolveInstalledDetailPresentation(detail: AgentSkillDetail) {
  const detailIconSource = isFeaturedSkill(detail)
    ? featuredSkillIcon(detail)
    : skillIcon(detail)
  const detailIconInvert = skillIconInvertInDark(detail)
  const detailVersionLabel = displaySkillVersion(detail.version)
  const detailUpdatedLabel = formatSkillUpdatedLabel(detail.updatedAt)
  const detailGithubUrl = skillGithubUrl(detail.name, detail.source)
  const detailAuthorUrl = skillAuthorUrl(detail.source)

  return {
    detailIconSource,
    detailIconInvert,
    detailVersionLabel,
    detailUpdatedLabel,
    detailGithubUrl,
    detailAuthorUrl
  }
}
