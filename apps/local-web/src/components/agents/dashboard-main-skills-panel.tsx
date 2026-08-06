import { navigateBack } from '@/lib/navigate-back'
import { catalogSkillDetailPath } from '@/lib/skills-catalog'

import { SkillsView } from './dashboard-main-views-lazy'
import type { DashboardMainViewsProps } from './dashboard-main-views-types'

export function DashboardMainSkillsPanel({
  client,
  navigate,
  skills,
  skillDetail,
  catalogSkillRoute,
  catalogSearchEnabled,
  isCatalogSearchPath,
  skillsViewMode,
  connecting,
  setSkillDetail,
  loadSkills
}: Pick<
  DashboardMainViewsProps,
  | 'client'
  | 'navigate'
  | 'skills'
  | 'skillDetail'
  | 'catalogSkillRoute'
  | 'catalogSearchEnabled'
  | 'isCatalogSearchPath'
  | 'skillsViewMode'
  | 'connecting'
  | 'setSkillDetail'
  | 'loadSkills'
>) {
  return (
    <SkillsView
      mode={skillsViewMode}
      skills={skills}
      loading={connecting && skills.length === 0}
      detail={skillDetail}
      catalogSkillRoute={catalogSkillRoute}
      catalogSearchEnabled={catalogSearchEnabled}
      openCatalogSearchInitially={isCatalogSearchPath}
      onOpen={name => navigate(`/dashboard/skills/${encodeURIComponent(name)}`)}
      onOpenCatalogDetail={skill => navigate(catalogSkillDetailPath(skill))}
      onBack={() => navigateBack(navigate, '/dashboard/skills')}
      onOpenImportGithub={() => navigate('/dashboard/skills/import/github')}
      onOpenImportFile={() => navigate('/dashboard/skills/import/file')}
      onOpenTrustedSources={() => navigate('/dashboard/skills/trusted/sources')}
      onOpenCatalogSetup={() => navigate('/dashboard/integrations/vercel')}
      onInstall={async source => {
        const installed = await client.installSkill(source)
        await loadSkills()
        return installed
      }}
      onUpload={async file => {
        await client.installSkillFile(file)
        await loadSkills()
      }}
      onLoadSuggestedSources={signal => client.listSkillSources(signal)}
      onSearchCatalog={(query, signal) =>
        client.searchSkillCatalog(query, 12, signal)
      }
      onListCatalogLeaderboard={async (view, options, signal) => {
        const result = await client.listSkillCatalogLeaderboard(
          {
            view,
            page: options?.page ?? 0,
            perPage: options?.perPage ?? 100
          },
          signal
        )
        return {
          data: result.data,
          total: result.total,
          allTimeTotal: result.allTimeTotal,
          hasMore:
            Boolean(result.hasMore) ||
            result.data.length >= (options?.perPage ?? 100),
          page: result.page
        }
      }}
      onGetCatalogDetail={(source, skill, signal) =>
        client.getCatalogSkillDetail(source, skill, signal)
      }
      onGetCatalogAudit={(source, skill, signal) =>
        client.getCatalogSkillAudit(source, skill, signal)
      }
      onBulkAction={async (action, names) => {
        const result = await client.bulkSkillAction(action, names)
        if (action === 'remove') {
          setSkillDetail(current =>
            current && result.succeeded.includes(current.name) ? null : current
          )
        } else if (
          skillDetail &&
          result.succeeded.includes(skillDetail.name)
        ) {
          const refreshed = await client.getSkill(skillDetail.name)
          setSkillDetail(refreshed)
        }
        await loadSkills()
        return result
      }}
      onSetEnabled={async (name, enabled) => {
        const updated = await client.setSkillEnabled(name, enabled)
        setSkillDetail(current =>
          current && current.name === name ? updated : current
        )
        await loadSkills()
      }}
      onRemove={async name => {
        await client.removeSkill(name)
        setSkillDetail(current =>
          current && current.name === name ? null : current
        )
        await loadSkills()
      }}
      onUpgrade={async () => {
        const installed = await client.upgradeSkills()
        await loadSkills()
        if (skillDetail) {
          try {
            const refreshed = await client.getSkill(skillDetail.name)
            setSkillDetail(refreshed)
          } catch {
            setSkillDetail(null)
          }
        }
        return installed
      }}
      depsHandlers={{
        getDeps: (name, signal) => client.getSkillDeps(name, signal),
        doctorDeps: (name, signal) => client.doctorSkillDeps(name, signal),
        installDeps: (name, options, signal) =>
          client.installSkillDeps(name, options, signal)
      }}
    />
  )
}
