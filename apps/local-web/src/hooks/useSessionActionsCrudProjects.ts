import type { AgentProject } from '@sandwalk/agent-ui-core'

import {
  writeLastSessionByScope,
  writeOpenTabsByProject,
  writeRecentProjectIds
} from '@/lib/app-storage'

import type { UseSessionActionsArgs } from './useSessionActionsTypes'

type ProjectCrudArgs = Pick<
  UseSessionActionsArgs,
  | 'client'
  | 'navigate'
  | 'activeProjectId'
  | 'activeProject'
  | 'setOpenTabsByProject'
  | 'setLastSessionByScope'
  | 'setProjectScopeId'
  | 'setRecentProjectIds'
  | 'loadProjects'
  | 'loadSessions'
  | 'setError'
>

export function useSessionActionsCrudProjects({
  client,
  navigate,
  activeProjectId,
  activeProject,
  setOpenTabsByProject,
  setLastSessionByScope,
  setProjectScopeId,
  setRecentProjectIds,
  loadProjects,
  loadSessions,
  setError
}: ProjectCrudArgs) {
  const createProject = async (input: {
    name: string
    description: string
    agentContext: string
    folderPath?: string | null
    icon?: string
    color?: string
  }) => {
    try {
      const project = await client.createProject({
        name: input.name,
        description: input.description || null,
        agentContext: input.agentContext || null,
        folderPath: input.folderPath || null,
        icon: input.icon,
        color: input.color
      })
      await loadProjects()
      setProjectScopeId(project.id)
      setRecentProjectIds(current => {
        const next = [
          project.id,
          ...current.filter(item => item !== project.id)
        ].slice(0, 10)
        writeRecentProjectIds(next)
        return next
      })
      navigate(`/projects/${project.id}`)
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to create project'
      )
      throw cause
    }
  }

  const saveProjectSettings = async (input: {
    name: string
    description: string
    agentContext: string
    folderPath?: string | null
    icon?: string
    color?: string
  }) => {
    if (!activeProject) return
    try {
      const folderPath =
        input.folderPath === undefined
          ? undefined
          : input.folderPath && input.folderPath.trim()
            ? input.folderPath.trim()
            : null
      await client.updateProject(activeProject.id, {
        name: input.name,
        description: input.description || null,
        agentContext: input.agentContext || null,
        ...(folderPath !== undefined ? { folderPath } : {}),
        icon: input.icon,
        color: input.color
      })
      await loadProjects()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update project'
      )
      throw cause
    }
  }

  const togglePinProject = async (project: AgentProject) => {
    try {
      await client.updateProject(project.id, { pinned: !project.pinned })
      await loadProjects()
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to update project'
      )
    }
  }

  const deleteProject = async (project: AgentProject) => {
    try {
      await client.deleteProject(project.id)
      setOpenTabsByProject(current => {
        if (!(project.id in current)) return current
        const next = { ...current }
        delete next[project.id]
        writeOpenTabsByProject(next)
        return next
      })
      setLastSessionByScope(current => {
        if (!(project.id in current)) return current
        const next = { ...current }
        delete next[project.id]
        writeLastSessionByScope(next)
        return next
      })
      if (activeProjectId === project.id) {
        setProjectScopeId(null)
        navigate('/')
      }
      await Promise.all([loadProjects(), loadSessions()])
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : 'Unable to delete project'
      )
    }
  }

  return {
    createProject,
    saveProjectSettings,
    togglePinProject,
    deleteProject
  }
}
