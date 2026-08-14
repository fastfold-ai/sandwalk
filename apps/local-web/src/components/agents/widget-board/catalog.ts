import type { WidgetCatalogEntry, WidgetType } from './types'

const ALL_SIZES = ['sm', 'md', 'lg'] as const
const BOTH = ['project', 'overview'] as const
const PROJECT = ['project'] as const

export const WIDGET_CATALOG: WidgetCatalogEntry[] = [
  {
    type: 'project-description',
    title: 'Project description',
    description: 'Project description text',
    kind: 'project',
    visual: 'card',
    defaultSize: 'lg',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...PROJECT]
  },
  {
    type: 'project-agent-context',
    title: 'Agent context',
    description: 'Extra context for the agent',
    kind: 'project',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...PROJECT]
  },
  {
    type: 'usage-hero',
    title: 'Usage',
    description: 'Lifetime tokens',
    kind: 'block',
    visual: 'card',
    defaultSize: 'lg',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-longest-agent',
    title: 'Longest agent',
    description: 'Longest contiguous agent activity',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-chats',
    title: 'Chats',
    description: 'Session count',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-longest-streak',
    title: 'Longest streak',
    description: 'Longest active-day streak',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-current-streak',
    title: 'Current streak',
    description: 'Current active-day streak',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'activity-heatmap',
    title: 'Activity',
    description: 'GitHub-style usage heatmap',
    kind: 'block',
    visual: 'plot',
    defaultSize: 'lg',
    allowedSizes: ['md', 'lg'],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-peak-day',
    title: 'Peak day',
    description: 'Highest token day',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-models-used',
    title: 'Models used',
    description: 'Distinct models',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-messages',
    title: 'Messages',
    description: 'Message count',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-tokens-in',
    title: 'Tokens in',
    description: 'Input tokens',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-tokens-out',
    title: 'Tokens out',
    description: 'Output tokens',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-cache-hit',
    title: 'Cache hit',
    description: 'Cache hit rate',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-avg-tokens-chat',
    title: 'Avg tokens / chat',
    description: 'Average tokens per session',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-runs',
    title: 'Runs',
    description: 'Agent run count',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'stat-files-count',
    title: 'Files count',
    description: 'Library + project folder files',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...PROJECT]
  },
  {
    type: 'stat-sites-count',
    title: 'Sites count',
    description: 'Sites linked to this project',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...PROJECT]
  },
  {
    type: 'stat-files-size',
    title: 'File size',
    description: 'Total Library artifacts size',
    kind: 'metric',
    visual: 'card',
    defaultSize: 'sm',
    allowedSizes: [...ALL_SIZES],
    surfaces: [...BOTH]
  },
  {
    type: 'models-chart',
    title: 'Model usage chart',
    description: 'Stacked model usage over the last 30 days',
    kind: 'block',
    visual: 'plot',
    defaultSize: 'lg',
    allowedSizes: ['md', 'lg'],
    surfaces: [...BOTH]
  },
  {
    type: 'models-top-list',
    title: 'Top models',
    description: 'Most used models with token breakdown',
    kind: 'block',
    visual: 'list',
    defaultSize: 'lg',
    allowedSizes: ['md', 'lg'],
    surfaces: [...BOTH]
  },
  {
    type: 'bench-results',
    title: 'Bench results',
    description: 'Benchmark runs for this project',
    kind: 'project',
    visual: 'list',
    defaultSize: 'lg',
    allowedSizes: ['md', 'lg'],
    surfaces: [...PROJECT]
  }
]

const byType = new Map(WIDGET_CATALOG.map(entry => [entry.type, entry]))

export function catalogEntry(type: string): WidgetCatalogEntry | undefined {
  return byType.get(type as WidgetType)
}

export function catalogForSurface(surface: 'project' | 'overview') {
  return WIDGET_CATALOG.filter(entry => entry.surfaces.includes(surface))
}
