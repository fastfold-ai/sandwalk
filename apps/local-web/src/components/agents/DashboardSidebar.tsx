import { ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { CapySidebarButton } from '@/components/agents/capy/CapySidebarButton'
import { SidebarUserMenu } from '@/components/agents/SidebarUserMenu'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { DRAFT_AGENT_SESSION_ID } from '@/lib/draft-agent'
import { cn } from '@/lib/utils'

import { DASHBOARD_NAV_GROUPS } from './dashboard-nav'
import type { DashboardSection } from './dashboard-section'

export type { DashboardSection } from './dashboard-section'

export function DashboardSidebar({
  active,
  userName,
  onLogout,
  onRefreshUser,
  backendVersion = null,
  backendUrl = null,
  connected = false
}: {
  active: DashboardSection
  userName: string | null
  onLogout?: () => void | Promise<void>
  onRefreshUser?: () => void | Promise<void>
  backendVersion?: string | null
  backendUrl?: string | null
  connected?: boolean
}) {
  const navigate = useNavigate()

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <ScrollArea className="flex-1">
        <nav className="space-y-4 p-3">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground h-8 w-full justify-start gap-2 px-2 text-[13px] font-normal"
            onClick={() => navigate(`/agents/${DRAFT_AGENT_SESSION_ID}`)}
          >
            <ArrowLeft className="size-3.5 shrink-0" />
            <span className="truncate">Back to Agents</span>
          </Button>
          {DASHBOARD_NAV_GROUPS.map((group, index) => (
            <div key={group.label ?? `group-${index}`} className="space-y-0.5">
              {group.label ? (
                <div className="text-muted-foreground/80 px-2 py-1 text-[11px] font-medium">
                  {group.label}
                </div>
              ) : null}
              {group.items.map(item => {
                const Icon = item.icon
                const selected = active === item.id
                return (
                  <button
                    key={item.id}
                    type="button"
                    className={cn(
                      'flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-[13px]',
                      selected
                        ? 'bg-sidebar-accent/55 text-sidebar-accent-foreground'
                        : 'text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground'
                    )}
                    onClick={() => navigate(item.path)}
                  >
                    <Icon className="size-3.5 shrink-0" />
                    {item.label}
                  </button>
                )
              })}
            </div>
          ))}
        </nav>
      </ScrollArea>

      <div className="shrink-0 p-2">
        <CapySidebarButton />
        <SidebarUserMenu
          userName={userName}
          onLogout={onLogout}
          onRefreshUser={onRefreshUser}
          backendVersion={backendVersion}
          backendUrl={backendUrl}
          connected={connected}
        />
      </div>
    </div>
  )
}
