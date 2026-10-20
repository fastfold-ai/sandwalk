import { navigateBack } from '@/lib/navigate-back'

import { HomeView, SpecialistsView } from './dashboard-main-views-lazy'
import type { DashboardMainViewsProps } from './dashboard-main-views-types'

export function DashboardMainSpecialistsPanel({
  client,
  navigate,
  health,
  activeProjectId,
  openSessionTab,
  loadSessions,
  specialistsViewMode,
  specialistsEditId,
  specialists,
  skills,
  mcpServers,
  mcpCatalog,
  specialistsLoading,
  connecting,
  loadSpecialists,
  loadSkills
}: Pick<
  DashboardMainViewsProps,
  | 'client'
  | 'navigate'
  | 'health'
  | 'activeProjectId'
  | 'openSessionTab'
  | 'loadSessions'
  | 'specialistsViewMode'
  | 'specialistsEditId'
  | 'specialists'
  | 'skills'
  | 'mcpServers'
  | 'mcpCatalog'
  | 'specialistsLoading'
  | 'connecting'
  | 'loadSpecialists'
  | 'loadSkills'
>) {
  return (
    <SpecialistsView
      mode={specialistsViewMode}
      specialistId={specialistsEditId}
      specialists={specialists}
      skills={skills}
      mcpServers={mcpServers}
      mcpCatalog={mcpCatalog}
      client={client}
      userName={health?.userName ?? null}
      loading={specialistsLoading || (connecting && specialists.length === 0)}
      onRefresh={loadSpecialists}
      onCreate={input => client.createSpecialist(input)}
      onUpdate={(id, input) => client.updateSpecialist(id, input)}
      onDelete={id => client.deleteSpecialist(id)}
      onOpenNew={() => navigate('/dashboard/specialists/new')}
      onOpenEdit={id =>
        navigate(`/dashboard/specialists/${encodeURIComponent(id)}`)
      }
      onStartChat={spec => {
        void client
          .createSession({
            title: `Chat with ${spec.name}`,
            projectId: activeProjectId,
            specialistId: spec.id,
            clientSurface: 'ui'
          })
          .then(async created => {
            await loadSessions()
            openSessionTab(created.id, activeProjectId ?? undefined)
            navigate(`/agents/${created.id}`)
          })
      }}
      onExploreBrain={spec => {
        navigate(`/dashboard/memory?scope=${encodeURIComponent(`specialist:${spec.id}`)}`)
      }}
      onOpenDefaults={() => navigate('/dashboard/memory?tab=settings')}
      onBack={() => navigateBack(navigate, '/dashboard/specialists')}
      onManageSkills={() => navigate('/dashboard/skills')}
      onManageMcps={() => navigate('/dashboard/mcp')}
      onOpenSkill={name =>
        navigate(`/dashboard/skills/${encodeURIComponent(name)}`)
      }
      onOpenMcp={({ kind, id }) => {
        const hash =
          kind === 'catalog'
            ? `catalog-${encodeURIComponent(id)}`
            : `server-${encodeURIComponent(id)}`
        navigate(`/dashboard/mcp#${hash}`)
      }}
      onEnableSkill={async name => {
        await client.setSkillEnabled(name, true)
        await loadSkills()
      }}
      onInstallSkill={async source => {
        await client.installSkill(source)
        await loadSkills()
      }}
      onListTools={signal => client.listTools({ signal })}
    />
  )
}

export function DashboardMainHomePanel({
  client,
  navigate,
  projects,
  sessions,
  sessionPreviews,
  loadSessionPreviews,
  health,
  activeProjectId,
  onCreateProject,
  createSession,
  onOpenProject,
  onOpenProjectSettings,
  togglePinProject,
  deleteProject
}: Pick<
  DashboardMainViewsProps,
  | 'client'
  | 'navigate'
  | 'projects'
  | 'sessions'
  | 'sessionPreviews'
  | 'loadSessionPreviews'
  | 'health'
  | 'activeProjectId'
  | 'onCreateProject'
  | 'createSession'
  | 'onOpenProject'
  | 'onOpenProjectSettings'
  | 'togglePinProject'
  | 'deleteProject'
>) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <HomeView
        client={client}
        projects={projects}
        sessions={sessions}
        previews={sessionPreviews}
        userName={health?.userName ?? null}
        activeProjectId={activeProjectId}
        onLoadPreviews={loadSessionPreviews}
        onCreateProject={onCreateProject}
        onCreateSession={projectId => void createSession(projectId)}
        onOpenProject={onOpenProject}
        onOpenProjectSettings={onOpenProjectSettings}
        onOpenSession={id => navigate(`/agents/${id}`)}
        onTogglePinProject={project => void togglePinProject(project)}
        onDeleteProject={project => void deleteProject(project)}
      />
    </div>
  )
}
