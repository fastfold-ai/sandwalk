import type {
  AgentCatalogSkill,
  AgentCatalogSkillAudit,
  AgentCatalogSkillDetail
} from '@sandwalk/agent-ui-core'
import { Loader } from 'lucide-react'

import { MarkdownContent } from '@/components/agents/MarkdownContent'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  catalogSkillInstallCommand,
  catalogSkillInstallTarget,
  frontmatterValue,
  skillsShSkillUrl,
  stripFrontmatter
} from '@/lib/skills-catalog'

import {
  InstallCommandBlock,
  SkillsBreadcrumb,
  SkillsShMetrics
} from './skills-view-shared'

export function SkillsCatalogDetailView({
  catalogSkillRoute,
  catalogDetail,
  catalogAudit,
  catalogDetailLoading,
  catalogDetailError,
  catalogInstallingId,
  installing,
  catalogInstallError,
  copiedCatalogInstall,
  isInstalled,
  onBack,
  onCopyInstall,
  onInstall
}: {
  catalogSkillRoute: { id: string; source: string; skill: string } | null
  catalogDetail: AgentCatalogSkillDetail | null
  catalogAudit: AgentCatalogSkillAudit | null
  catalogDetailLoading: boolean
  catalogDetailError: string | null
  catalogInstallingId: string | null
  installing: boolean
  catalogInstallError: string | null
  copiedCatalogInstall: boolean
  isInstalled: (skill: AgentCatalogSkill) => boolean
  onBack: () => void
  onCopyInstall: () => void
  onInstall: () => void
}) {
  const catalogSource = String(
    catalogDetail?.source || catalogSkillRoute?.source || ''
  ).trim()
  const catalogSlug = String(
    catalogDetail?.slug || catalogSkillRoute?.skill || ''
  ).trim()
  const catalogId = String(catalogDetail?.id || catalogSkillRoute?.id || '').trim()
  const catalogFiles = catalogDetail?.files || []
  const catalogSkillMd = (
    catalogFiles.find(file => file.path.toLowerCase() === 'skill.md') ||
    catalogFiles.find(file => file.path.toLowerCase().endsWith('/skill.md'))
  )?.contents
  const catalogSummary =
    (catalogSkillMd ? frontmatterValue(catalogSkillMd, 'description') : null) ||
    (catalogSkillMd
      ? stripFrontmatter(catalogSkillMd)
          .split('\n')
          .map(line => line.trim())
          .find(line => line && !line.startsWith('#') && !line.startsWith('-'))
      : null) ||
    'No summary available.'
  const catalogInstallCommand =
    catalogSource && catalogSlug
      ? catalogSkillInstallCommand(catalogSource, catalogSlug, catalogFiles)
      : ''
  const catalogInstallTarget =
    catalogSource && catalogSlug
      ? catalogSkillInstallTarget(catalogSource, catalogSlug, catalogFiles)
      : ''
  const catalogInstalls = Number(catalogDetail?.installs || 0)
  const catalogAudits = catalogAudit?.audits || []
  const catalogSkillsShUrl = catalogSource
    ? skillsShSkillUrl(
        catalogSource,
        String(
          catalogSkillRoute?.skill || catalogDetail?.slug || catalogSlug || ''
        )
      )
    : null

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 md:p-6">
        <div className="flex items-center justify-between gap-3">
          <SkillsBreadcrumb onBack={onBack} />
          {catalogSkillsShUrl ? (
            <a
              href={catalogSkillsShUrl}
              target="_blank"
              rel="noreferrer"
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border/70 px-3 py-1.5 text-xs hover:bg-muted"
            >
              <img
                src="/suggestions/skills-sh.png"
                alt=""
                className="size-3.5 rounded object-contain dark:invert"
              />
              View in Skills.sh
            </a>
          ) : null}
        </div>
        {catalogDetailLoading ? (
          <div className="text-muted-foreground flex min-h-[40vh] items-center justify-center gap-2 text-sm">
            <Loader className="size-4 shrink-0 animate-spin" aria-hidden />
            <span>Fetching Skills.sh metadata</span>
          </div>
        ) : catalogDetailError ? (
          <p className="text-destructive text-sm">{catalogDetailError}</p>
        ) : (
          <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_250px]">
            <section className="space-y-4">
              <div>
                <p className="text-muted-foreground text-xs">
                  skills / {catalogSource || 'unknown'} / {catalogSlug || 'unknown'}
                </p>
                <h1 className="mt-2 text-3xl font-semibold">
                  {catalogSlug || 'Catalog skill'}
                </h1>
              </div>

              <div className="space-y-2">
                <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                  Installation
                </p>
                <InstallCommandBlock
                  command={catalogInstallCommand || 'No install command available.'}
                  copied={copiedCatalogInstall}
                  onCopy={onCopyInstall}
                />
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    disabled={!catalogInstallTarget || installing}
                    onClick={onInstall}
                  >
                    {installing && catalogInstallingId === (catalogId || 'catalog-detail')
                      ? 'Installing…'
                      : isInstalled({
                          id: catalogId,
                          slug: catalogSlug,
                          name: catalogSlug,
                          source: catalogSource,
                          installs: catalogInstalls,
                          sourceType: 'github',
                          installUrl: null,
                          url: null
                        })
                      ? 'Update'
                      : 'Install'}
                  </Button>
                </div>
                {catalogInstallError ? (
                  <div
                    role="alert"
                    className="border-destructive/30 bg-destructive/5 text-destructive rounded-lg border px-3 py-2 text-sm leading-relaxed"
                  >
                    {catalogInstallError}
                  </div>
                ) : null}
              </div>

              <div className="space-y-2">
                <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                  Summary
                </p>
                <div className="bg-card rounded-lg border p-3 text-sm leading-relaxed">
                  {catalogSummary}
                </div>
              </div>

              {catalogSkillMd ? (
                <section className="space-y-2">
                  <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                    SKILL.md
                  </p>
                  <MarkdownContent
                    content={stripFrontmatter(catalogSkillMd)}
                    className="max-w-none text-sm [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_code]:break-words [&_table]:block [&_table]:max-w-full [&_table]:overflow-x-auto"
                  />
                </section>
              ) : null}
            </section>

            <SkillsShMetrics
              source={catalogSource}
              installs={catalogInstalls}
              audits={catalogAudits}
            />
          </div>
        )}
      </div>
    </ScrollArea>
  )
}
