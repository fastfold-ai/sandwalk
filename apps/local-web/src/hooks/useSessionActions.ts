import { useSessionActionsCrud } from './useSessionActionsCrud'
import { useSessionActionsSelection } from './useSessionActionsSelection'
import { useSessionActionsTabs } from './useSessionActionsTabs'
import type { UseSessionActionsArgs } from './useSessionActionsTypes'

export type { UseSessionActionsArgs } from './useSessionActionsTypes'

export function useSessionActions(args: UseSessionActionsArgs) {
  const crud = useSessionActionsCrud(args)
  const tabs = useSessionActionsTabs(args)
  const selection = useSessionActionsSelection({
    client: args.client,
    sessions: args.sessions,
    loadSessions: args.loadSessions,
    setError: args.setError,
    setCollapsedSidebarSections: args.setCollapsedSidebarSections,
    deleteSession: crud.deleteSession,
    exportTranscript: crud.exportTranscript
  })

  return {
    ...crud,
    ...tabs,
    ...selection
  }
}
