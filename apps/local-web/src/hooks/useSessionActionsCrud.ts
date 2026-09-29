import { useSessionActionsCrudProjects } from './useSessionActionsCrudProjects'
import { useSessionActionsCrudSessions } from './useSessionActionsCrudSessions'
import type { UseSessionActionsArgs } from './useSessionActionsTypes'

// Everything except the render-time `sessions` array, which only the
// selection hook needs — lets split panes reuse crud without it.
type UseSessionActionsCrudArgs = Omit<
  UseSessionActionsArgs,
  'sessions' | 'tabGroups' | 'tabGroupsRef' | 'lastSessionByScope'
>

export function useSessionActionsCrud(args: UseSessionActionsCrudArgs) {
  const projects = useSessionActionsCrudProjects(args)
  const sessions = useSessionActionsCrudSessions(args)

  return {
    ...sessions,
    ...projects
  }
}
