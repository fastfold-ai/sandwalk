import { validateIntegrationOrProbeModal } from '@/lib/app-helpers'
import { catalogSkillDetailPath } from '@/lib/skills-catalog'

import {
  navigateToIntegration,
  openVercelIntegrationTerminal
} from './dashboard-main-view-helpers'
import type { DashboardMainViewsProps } from './dashboard-main-views-types'
import {
  DashboardOverviewView,
  IntegrationsView,
  McpView,
  SkillsView
} from './dashboard-main-views-lazy'

export function DashboardMainOverviewPanel({
  client,
  navigate,
  sessions,
  activeProjectId,
  skills,
  integrations,
  catalogSearchEnabled,
  connecting,
  mcpServers,
  mcpCatalog,
  mcpCatalogLoading,
  loadSkills,
  loadIntegrations,
  loadMcpServers,
  refreshMcp,
  loadSessions
}: Pick<
  DashboardMainViewsProps,
  | 'client'
  | 'navigate'
  | 'sessions'
  | 'activeProjectId'
  | 'skills'
  | 'integrations'
  | 'catalogSearchEnabled'
  | 'connecting'
  | 'mcpServers'
  | 'mcpCatalog'
  | 'mcpCatalogLoading'
  | 'loadSkills'
  | 'loadIntegrations'
  | 'loadMcpServers'
  | 'refreshMcp'
  | 'loadSessions'
>) {
  return (
    <DashboardOverviewView sessions={sessions}>
      <SkillsView
        featuredOnly
        mode="list"
        skills={skills}
        loading={connecting && skills.length === 0}
        detail={null}
        catalogSkillRoute={null}
        catalogSearchEnabled={catalogSearchEnabled}
        onShowAll={() => navigate('/dashboard/skills')}
        onOpen={name =>
          navigate(`/dashboard/skills/${encodeURIComponent(name)}`)
        }
        onOpenCatalogDetail={skill => navigate(catalogSkillDetailPath(skill))}
        onBack={() => navigate('/dashboard/skills')}
        onOpenImportGithub={() => navigate('/dashboard/skills/import/github')}
        onOpenImportFile={() => navigate('/dashboard/skills/import/file')}
        onOpenTrustedSources={() =>
          navigate('/dashboard/skills/trusted/sources')
        }
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
          await loadSkills()
          return result
        }}
        onSetEnabled={async (name, enabled) => {
          await client.setSkillEnabled(name, enabled)
          await loadSkills()
        }}
        onRemove={async name => {
          await client.removeSkill(name)
          await loadSkills()
        }}
      />
      <McpView
        featuredOnly
        mcpServers={mcpServers}
        catalog={mcpCatalog}
        catalogLoading={mcpCatalogLoading}
        onShowAll={() => navigate('/dashboard/mcp')}
        onRefresh={refreshMcp}
        onConnectCatalog={async (catalogId, input) => {
          const result = await client.connectMcpCatalog(catalogId, input)
          await refreshMcp()
          await loadIntegrations()
          return result
        }}
        onToggleCatalog={async (entry, enabled) => {
          await client.setMcpCatalogEnabled(entry.id, enabled)
          await refreshMcp()
        }}
        onCreateMcp={async input => {
          await client.createMcpServer(input)
          await loadMcpServers()
        }}
        onDeleteMcp={async id => {
          await client.deleteMcpServer(id)
          await loadMcpServers()
        }}
        onToggleCustom={async (id, enabled) => {
          await client.updateMcpServer(id, { enabled })
          await loadMcpServers()
        }}
        onOpenCatalog={entry =>
          navigate(`/dashboard/mcp/catalog/${encodeURIComponent(entry.id)}`)
        }
      />
      <IntegrationsView
        featuredOnly
        terminalClient={client}
        integrations={integrations}
        loading={connecting && integrations.length === 0}
        selectedKey={null}
        values={{}}
        onShowAll={() => navigate('/dashboard/integrations')}
        onValueChange={() => {}}
        onSelect={key => navigateToIntegration(navigate, integrations, key)}
        onSave={async () => {}}
        onValidate={async key => validateIntegrationOrProbeModal(client, key)}
        onAutofill={async key => {
          await client.autofillIntegration(key)
          await loadIntegrations()
        }}
        onSetup={async key => {
          const result = await client.setupIntegration(key)
          await loadIntegrations()
          return result
        }}
        onOpenVercelTerminal={() =>
          openVercelIntegrationTerminal({
            client,
            sessions,
            activeProjectId,
            loadSessions
          })
        }
        onRemove={async key => {
          await client.removeIntegration(key)
          await loadIntegrations()
        }}
      />
    </DashboardOverviewView>
  )
}
