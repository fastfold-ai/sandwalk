import type { AgentSkillDetail } from '@sandwalk/agent-ui-core'

import { DetailPageSkeleton } from '@/components/agents/PageSkeletons'
import { ScrollArea } from '@/components/ui/scroll-area'

import { SkillsInstalledDetailView } from './skills-view-installed-detail'
import { SkillsBreadcrumb } from './skills-view-shared'
import type { useSkillsViewState } from './use-skills-view-state'

export function SkillsViewDetailMode({
  detail,
  catalogSearchEnabled,
  state,
  onBack
}: {
  detail: AgentSkillDetail
  catalogSearchEnabled: boolean
  state: ReturnType<typeof useSkillsViewState>
  onBack: () => void
}) {
  if (!state.detailPresentation) {
    return (
      <ScrollArea className="flex-1">
        <div className="mx-auto w-full max-w-3xl px-6 pt-3 pb-8 md:px-10">
          <SkillsBreadcrumb onBack={onBack} />
          <DetailPageSkeleton bare />
        </div>
      </ScrollArea>
    )
  }

  return (
    <SkillsInstalledDetailView
      detail={detail}
      catalogSearchEnabled={catalogSearchEnabled}
      localCatalogDetail={state.localCatalogDetail}
      localCatalogAudit={state.localCatalogAudit}
      localCatalogLoading={state.localCatalogLoading}
      detailInstallCommand={state.detailInstallCommand}
      detailGithubUrl={state.detailPresentation.detailGithubUrl}
      detailAuthorUrl={state.detailPresentation.detailAuthorUrl}
      detailIconSource={state.detailPresentation.detailIconSource}
      detailIconInvert={state.detailPresentation.detailIconInvert}
      detailVersionLabel={state.detailPresentation.detailVersionLabel}
      detailUpdatedLabel={state.detailPresentation.detailUpdatedLabel}
      updateAvailable={state.detailPresentation.updateAvailable}
      latestVersionLabel={state.detailPresentation.latestVersionLabel}
      copiedInstall={state.copiedInstall}
      pendingEnabled={state.pendingEnabled}
      pendingRemove={state.pendingRemove}
      pendingUpgrade={state.pendingUpgrade}
      batchBusy={state.batchBusy}
      batchToast={state.batchToast}
      removeTarget={state.removeTarget}
      onBack={onBack}
      onCopyInstall={state.handleCopyInstall}
      onUpgrade={() => void state.upgradeSkills()}
      onRemove={state.removeSkill}
      onRemoveDialogOpenChange={state.handleRemoveDialogOpenChange}
      onConfirmRemove={() => void state.confirmRemoveSkill()}
      onToggleEnabled={(name, enabled) => void state.setSkillEnabled(name, enabled)}
    />
  )
}
