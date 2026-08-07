import {
  Box,
  Boxes,
  Container,
  Cpu,
  Database,
  GitBranch,
  HardDrive,
  LayoutDashboard,
  Mic,
  Paintbrush,
  Plug,
  ScrollText,
  Settings2,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Target,
  Wrench
} from 'lucide-react'
import type { ComponentType } from 'react'

import { McpMark } from '@/components/McpMark'

import type { DashboardSection } from './dashboard-section'

export type DashboardNavItem = {
  id: DashboardSection
  label: string
  path: string
  icon: ComponentType<{ className?: string }>
}

export type DashboardNavGroup = {
  label: string | null
  items: DashboardNavItem[]
}

export const DASHBOARD_NAV_GROUPS: DashboardNavGroup[] = [
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
      {
        id: 'appearance',
        label: 'Appearance',
        path: '/dashboard/appearance',
        icon: Paintbrush
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
        id: 'agent_security',
        label: 'Security',
        path: '/dashboard/agent/security',
        icon: ShieldCheck
      },
      {
        id: 'context',
        label: 'Context',
        path: '/dashboard/context',
        icon: ScrollText
      },
      {
        id: 'voice',
        label: 'Voice',
        path: '/dashboard/voice',
        icon: Mic
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
        id: 'bench',
        label: 'Benchmarking',
        path: '/dashboard/bench',
        icon: Target
      },
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
