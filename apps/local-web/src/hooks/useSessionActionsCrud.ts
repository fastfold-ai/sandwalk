import { useSessionActionsCrudProjects } from './useSessionActionsCrudProjects'
import { useSessionActionsCrudSessions } from './useSessionActionsCrudSessions'

import type { UseSessionActionsArgs } from './useSessionActionsTypes'

type UseSessionActionsCrudArgs = UseSessionActionsArgs

export function useSessionActionsCrud(args: UseSessionActionsCrudArgs) {
  const projects = useSessionActionsCrudProjects(args)
  const sessions = useSessionActionsCrudSessions(args)

  return {
    ...sessions,
    ...projects
  }
}
