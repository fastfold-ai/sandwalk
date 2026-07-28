import { lazy } from 'react'

/*
 * AgentSandboxView, DataView, McpView, and SpecialistsView are also imported
 * statically elsewhere (Onboarding*Step components, SpecialistAvatar
 * consumers) — Rolldown/Vite can't split them into separate chunks in that
 * case (INEFFECTIVE_DYNAMIC_IMPORT), so they're re-exported eagerly here
 * instead of wrapped in `lazy()`. They still render fine inside the
 * Suspense boundaries below since those tolerate regular components too.
 */
export { AgentSandboxView } from '@/components/agents/AgentSandboxView'
export { DataView } from '@/components/agents/DataView'
export { McpView } from '@/components/agents/McpView'
export { SpecialistsView } from '@/components/agents/SpecialistsView'

export const AgentRuntimeView = lazy(() =>
  import('@/components/agents/AgentRuntimeView').then(m => ({
    default: m.AgentRuntimeView
  }))
)
export const AgentPromptsView = lazy(() =>
  import('@/components/agents/AgentPromptsView').then(m => ({
    default: m.AgentPromptsView
  }))
)
export const AgentSecurityView = lazy(() =>
  import('@/components/agents/AgentSecurityView').then(m => ({
    default: m.AgentSecurityView
  }))
)
export const AppearanceView = lazy(() =>
  import('@/components/agents/AppearanceView').then(m => ({
    default: m.AppearanceView
  }))
)
export const DashboardOverviewView = lazy(() =>
  import('@/components/agents/DashboardOverviewView').then(m => ({
    default: m.DashboardOverviewView
  }))
)
export const DoctorView = lazy(() =>
  import('@/components/agents/DoctorView').then(m => ({ default: m.DoctorView }))
)
export const EnvironmentView = lazy(() =>
  import('@/components/agents/EnvironmentView').then(m => ({
    default: m.EnvironmentView
  }))
)
export const GeneralView = lazy(() =>
  import('@/components/agents/GeneralView').then(m => ({
    default: m.GeneralView
  }))
)
export const HomeView = lazy(() =>
  import('@/components/agents/HomeView').then(m => ({ default: m.HomeView }))
)
export const IntegrationsView = lazy(() =>
  import('@/components/agents/IntegrationsView').then(m => ({
    default: m.IntegrationsView
  }))
)
export const McpDetailView = lazy(() =>
  import('@/components/agents/McpDetailView').then(m => ({
    default: m.McpDetailView
  }))
)
export const SandboxListView = lazy(() =>
  import('@/components/agents/SandboxListView').then(m => ({
    default: m.SandboxListView
  }))
)
export const ModelsView = lazy(() =>
  import('@/components/agents/ModelsView').then(m => ({
    default: m.ModelsView
  }))
)
export const ServerStatusView = lazy(() =>
  import('@/components/agents/ServerStatusView').then(m => ({
    default: m.ServerStatusView
  }))
)
export const ServerNetworkView = lazy(() =>
  import('@/components/agents/ServerNetworkView').then(m => ({
    default: m.ServerNetworkView
  }))
)
export const ServerAdvancedView = lazy(() =>
  import('@/components/agents/ServerAdvancedView').then(m => ({
    default: m.ServerAdvancedView
  }))
)
export const ServerSecurityView = lazy(() =>
  import('@/components/agents/ServerSecurityView').then(m => ({
    default: m.ServerSecurityView
  }))
)
export const ServerLogsView = lazy(() =>
  import('@/components/agents/ServerLogsView').then(m => ({
    default: m.ServerLogsView
  }))
)
export const SkillsView = lazy(() =>
  import('@/components/agents/SkillsView').then(m => ({ default: m.SkillsView }))
)
export const StorageView = lazy(() =>
  import('@/components/agents/StorageView').then(m => ({
    default: m.StorageView
  }))
)
export const ToolsView = lazy(() =>
  import('@/components/agents/ToolsView').then(m => ({ default: m.ToolsView }))
)
export const VoiceView = lazy(() =>
  import('@/components/agents/VoiceView').then(m => ({ default: m.VoiceView }))
)
export const LibraryView = lazy(() =>
  import('@/components/agents/LibraryView').then(m => ({
    default: m.LibraryView
  }))
)
