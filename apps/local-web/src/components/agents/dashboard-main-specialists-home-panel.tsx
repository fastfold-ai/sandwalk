import { navigateBack } from '@/lib/navigate-back'

import type { DashboardMainViewsProps } from './dashboard-main-views-types'
import { HomeView, SpecialistsView } from './dashboard-main-views-lazy'

export function DashboardMainSpecialistsPanel({
  client,
  navigate,
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
      loading={specialistsLoading || (connecting && specialists.length === 0)}
      onRefresh={loadSpecialists}
      onCreate={input => client.createSpecialist(input)}
      onUpdate={(id, input) => client.updateSpecialist(id, input)}
      onDelete={id => client.deleteSpecialist(id)}
      onOpenNew={() => navigate('/dashboard/specialists/new')}
      onOpenEdit={id =>
        navigate(`/dashboard/specialists/${encodeURIComponent(id)}`)
      }
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
  togglePinProject,
  deleteProject
}: Pick<
  DashboardMainViewsProps,
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
  | 'togglePinProject'
  | 'deleteProject'
>) {
  return (
    <HomeView
      projects={projects}
      sessions={sessions}
      previews={sessionPreviews}
      userName={health?.userName ?? null}
      activeProjectId={activeProjectId}
      onLoadPreviews={loadSessionPreviews}
      onCreateProject={onCreateProject}
      onCreateSession={projectId => void createSession(projectId)}
      onOpenProject={onOpenProject}
      onOpenSession={id => navigate(`/agents/${id}`)}
      onTogglePinProject={project => void togglePinProject(project)}
      onDeleteProject={project => void deleteProject(project)}
    />
  )
}
