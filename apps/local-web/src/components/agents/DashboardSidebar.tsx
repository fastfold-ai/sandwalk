import {
  ArrowLeft,
  Box,
  Boxes,
  Container,
  Cpu,
  Database,
  GitBranch,
  HardDrive,
  LayoutDashboard,
  MessageSquareText,
  PanelLeft,
  Plug,
  Settings2,
  Sparkles,
  Stethoscope,
  Wrench
} from 'lucide-react'
import type { ComponentType } from 'react'
import { useNavigate } from 'react-router-dom'

import { SidebarUserMenu } from '@/components/agents/SidebarUserMenu'
import { McpMark } from '@/components/McpMark'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

export type DashboardSection =
  | 'overview'
  | 'general'
  | 'agent_runtime'
  | 'agent_sandbox'
  | 'agent_prompts'
  | 'models'
  | 'datasets'
  | 'tools'
  | 'doctor'
  | 'storage'
  | 'environment'
  | 'skills'
  | 'integrations'
  | 'mcp'
  | 'specialists'

type NavItem = {
  id: DashboardSection
  label: string
  path: string
  icon: ComponentType<{ className?: string }>
}

const NAV_GROUPS: Array<{ label: string | null; items: NavItem[] }> = [
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
      }
    ]
  },
  {
    label: 'Agent',
    items: [
      {
        id: 'agent_runtime',
        label: 'Runtime',
        path: '/dashboard/agent/runtime',
        icon: Cpu
      },
      {
        id: 'agent_sandbox',
        label: 'Sandbox',
        path: '/dashboard/agent/sandbox',
        icon: Container
      },
      {
        id: 'agent_prompts',
        label: 'Prompts',
        path: '/dashboard/agent/prompts',
        icon: MessageSquareText
      }
    ]
  },
  {
    label: 'Capabilities',
    items: [
      { id: 'models', label: 'Models', path: '/dashboard/models', icon: Box },
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
        id: 'specialists',
        label: 'Specialists',
        path: '/dashboard/specialists',
        icon: GitBranch
      },
      {
        id: 'integrations',
        label: 'Integrations',
        path: '/dashboard/integrations',
        icon: Plug
      },
      { id: 'mcp', label: 'MCPs', path: '/dashboard/mcp', icon: McpMark }
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
  onCollapse,
  onLogout,
  onRefreshUser,
  backendVersion = null,
  backendUrl = null,
  connected = false
}: {
  active: DashboardSection
  userName: string | null
  onCollapse: () => void
  onLogout?: () => void | Promise<void>
  onRefreshUser?: () => void | Promise<void>
  backendVersion?: string | null
  backendUrl?: string | null
  connected?: boolean
}) {
  const navigate = useNavigate()

  return (
    <div className="flex h-full w-full flex-col overflow-hidden">
      <div className="sandwalk-sidebar-chrome shrink-0 border-b p-3">
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
