import { DashboardOverviewView } from './dashboard-main-views-lazy'
import type { DashboardMainViewsProps } from './dashboard-main-views-types'

export function DashboardMainOverviewPanel({
  client,
  sessions
}: Pick<DashboardMainViewsProps, 'client' | 'sessions'>) {
  return <DashboardOverviewView sessions={sessions} client={client} />
}
