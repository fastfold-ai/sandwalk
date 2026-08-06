import { copyText } from '@/lib/clipboard'
import {
  catalogSkillInstallCommand,
  catalogSkillInstallTarget
} from '@/lib/skills-catalog'

import { SkillsCatalogDetailView } from './skills-view-catalog-detail'
import type { SkillDepsHandlers } from './skills-view-detail-deps'
import {
  SkillsImportFileView,
  SkillsImportGithubView,
  SkillsTrustedSourcesView
} from './skills-view-import-views'
import type { useSkillsViewState } from './use-skills-view-state'

export function SkillsViewCatalogMode({
  state,
  catalogSkillRoute,
  onBack,
  depsHandlers = null
}: {
  state: ReturnType<typeof useSkillsViewState>
  catalogSkillRoute: { id: string; source: string; skill: string } | null
  onBack: () => void
  depsHandlers?: SkillDepsHandlers | null
}) {
  const catalogSource = String(
    state.catalogDetail?.source || catalogSkillRoute?.source || ''
  ).trim()
  const catalogSlug = String(
    state.catalogDetail?.slug || catalogSkillRoute?.skill || ''
  ).trim()
  const catalogFiles = state.catalogDetail?.files || []
  const catalogInstallTarget =
    catalogSource && catalogSlug
      ? catalogSkillInstallTarget(catalogSource, catalogSlug, catalogFiles)
      : ''
  const catalogInstallCommand =
    catalogSource && catalogSlug
      ? catalogSkillInstallCommand(catalogSource, catalogSlug, catalogFiles)
      : ''

  return (
    <SkillsCatalogDetailView
      catalogSkillRoute={catalogSkillRoute}
      catalogDetail={state.catalogDetail}
      catalogAudit={state.catalogAudit}
      catalogDetailLoading={state.catalogDetailLoading}
      catalogDetailError={state.catalogDetailError}
      catalogInstallingId={state.catalogInstallingId}
      installing={state.installing}
      catalogInstallError={state.catalogInstallError}
      copiedCatalogInstall={state.copiedCatalogInstall}
      isInstalled={state.checkCatalogSkillInstalled}
      onBack={onBack}
      onCopyInstall={() => {
        if (!catalogInstallCommand) return
        void copyText(catalogInstallCommand).then(() => {
          state.setCopiedCatalogInstall(true)
        })
      }}
      onInstall={() =>
        void state.submitCatalogInstallSource(
          catalogInstallTarget,
          String(state.catalogDetail?.id || catalogSkillRoute?.id || '').trim() ||
            'catalog-detail',
          catalogSlug
        )
      }
      depsHandlers={depsHandlers}
    />
  )
}

export function SkillsViewImportGithubMode({
  state,
  onBack
}: {
  state: ReturnType<typeof useSkillsViewState>
  onBack: () => void
}) {
  return (
    <SkillsImportGithubView
      githubSource={state.githubSource}
      onGithubSourceChange={state.setGithubSource}
      installing={state.installing}
      onBack={onBack}
      onSubmit={() => void state.submitGithubInstall()}
    />
  )
}

export function SkillsViewImportFileMode({
  state,
  onBack
}: {
  state: ReturnType<typeof useSkillsViewState>
  onBack: () => void
}) {
  return (
    <SkillsImportFileView
      uploadFile={state.uploadFile}
      uploadInputRef={state.uploadInputRef}
      onUploadFileChange={state.setUploadFile}
      installing={state.installing}
      onBack={onBack}
      onSubmit={() => void state.submitFileInstall()}
    />
  )
}

export function SkillsViewTrustedSourcesMode({
  state,
  onBack
}: {
  state: ReturnType<typeof useSkillsViewState>
  onBack: () => void
}) {
  return (
    <SkillsTrustedSourcesView
      trustedSources={state.trustedSources}
      trustedSelected={state.trustedSelected}
      onTrustedSelectedChange={state.setTrustedSelected}
      trustedLoading={state.trustedLoading}
      selectedTrustedSources={state.selectedTrustedSources}
      installing={state.installing}
      onBack={onBack}
      onSubmit={() => void state.submitTrustedInstall()}
    />
  )
}
