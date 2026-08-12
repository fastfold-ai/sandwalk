import type { WidgetLayout, WidgetSize } from '@sandwalk/agent-ui-core'

export type { WidgetLayout, WidgetSize }

export type WidgetSurface = 'project' | 'overview'

export type WidgetType =
  | 'usage-hero'
  | 'stat-longest-agent'
  | 'stat-chats'
  | 'stat-longest-streak'
  | 'stat-current-streak'
  | 'activity-heatmap'
  | 'stat-peak-day'
  | 'stat-models-used'
  | 'stat-messages'
  | 'stat-tokens-in'
  | 'stat-tokens-out'
  | 'stat-cache-hit'
  | 'stat-avg-tokens-chat'
  | 'stat-runs'
  | 'models-chart'
  | 'models-top-list'
  | 'bench-results'

export type WidgetKind = 'metric' | 'block' | 'project'

/** Visual affordance in the Add widget picker. */
export type WidgetVisual = 'card' | 'plot' | 'list'

export type WidgetCatalogEntry = {
  type: WidgetType
  title: string
  description: string
  kind: WidgetKind
  visual: WidgetVisual
  defaultSize: WidgetSize
  allowedSizes: WidgetSize[]
  surfaces: WidgetSurface[]
}
