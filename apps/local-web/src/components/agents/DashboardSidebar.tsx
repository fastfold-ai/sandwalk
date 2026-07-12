import {
  ArrowLeft,
  Activity,
  Box,
  Boxes,
  Database,
  HardDrive,
  LayoutDashboard,
  Network,
  PanelLeft,
  Plug,
  Settings2,
  Sparkles,
  Stethoscope,
  Wrench
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'

import { SidebarUserMenu } from '@/components/agents/SidebarUserMenu'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

export type DashboardSection =
  | 'overview'
  | 'status'
  | 'general'
  | 'models'
  | 'datasets'
  | 'tools'
  | 'doctor'
  | 'storage'
  | 'environment'
  | 'skills'
  | 'integrations'
  | 'mcp'

type NavItem = {
  id: DashboardSection
  label: string
  path: string
  icon: typeof LayoutDashboard
}

const NAV_GROUPS: Array<{ label: string | null; items: NavItem[] }> = [
  {
    label: 'Server',
    items: [
      {
        id: 'status',
        label: 'Status',
        path: '/dashboard/status',
        icon: Activity
      }
    ]
  },
  {
    label: null,
    items: [
      {
        id: 'overview',
        label: 'Overview',
        path: '/dashboard',
        icon: LayoutDashboard
      },
      {
        id: 'general',
        label: 'General',
        path: '/dashboard/general',
        icon: Settings2
      },
      { id: 'models', label: 'Models', path: '/dashboard/models', icon: Box }
    ]
  },
  {
    label: 'Tools & Integrations',
    items: [
      { id: 'tools', label: 'Tools', path: '/dashboard/tools', icon: Wrench },
      {
        id: 'datasets',
        label: 'Datasets',
        path: '/dashboard/datasets',
        icon: Database
      },
      {
        id: 'skills',
        label: 'Skills',
        path: '/dashboard/skills',
        icon: Sparkles
      },
      {
        id: 'integrations',
        label: 'Integrations',
        path: '/dashboard/integrations',
        icon: Plug
      },
      { id: 'mcp', label: 'MCPs', path: '/dashboard/mcp', icon: Network }
    ]
  },
  {
    label: 'Workspace',
    items: [
      {
        id: 'doctor',
        label: 'Doctor',
        path: '/dashboard/doctor',
        icon: Stethoscope
      },
      {
        id: 'storage',
        label: 'Storage',
        path: '/dashboard/storage',
        icon: HardDrive
      },
      {
        id: 'environment',
        label: 'Environment',
        path: '/dashboard/environment',
        icon: Boxes
      }
    ]
  }
]

export function DashboardSidebar({
  active,
  userName,
  onCollapse
}: {
  active: DashboardSection
  userName: string | null
  onCollapse: () => void
}) {
  const navigate = useNavigate()

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="shrink-0 border-b p-3">
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="hover:bg-sidebar-accent/70 text-muted-foreground hover:text-foreground inline-flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px]"
            onClick={() => navigate('/')}
          >
            <ArrowLeft className="size-3.5 shrink-0" />
            <span className="truncate">Back to Agents</span>
          </button>
          <Button
            variant="ghost"
            size="icon"
            className="size-8 shrink-0"
            onClick={onCollapse}
            aria-label="Hide sidebar"
          >
            <PanelLeft className="size-4" />
          </Button>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <nav className="space-y-4 p-3">
          {NAV_GROUPS.map((group, index) => (
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
                      'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px]',
                      selected
                        ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                        : 'text-muted-foreground hover:bg-sidebar-accent/70 hover:text-foreground'
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
        <SidebarUserMenu userName={userName} />
      </div>
    </div>
  )
}
