import type { WidgetLayout, WidgetLayoutItem, WidgetSize } from '@sandwalk/agent-ui-core'

import { catalogEntry } from './catalog'
import type { WidgetType } from './types'

/** Bumped when Project Home default seed changes. */
export const LAYOUT_VERSION = 6
/** Bumped when Dashboard Overview default seed changes. */
export const OVERVIEW_LAYOUT_VERSION = 7

function item(type: WidgetType, size?: WidgetSize): WidgetLayoutItem {
  const entry = catalogEntry(type)
  return {
    id: crypto.randomUUID(),
    type,
    size: size || entry?.defaultSize || 'sm'
  }
}

/** Project Home seed: description → usage → streak metrics → activity → bench. */
export function createDefaultProjectHomeLayout(): WidgetLayout {
  return {
    version: LAYOUT_VERSION,
    widgets: [
      item('project-description', 'lg'),
      item('usage-hero', 'lg'),
      item('stat-longest-agent', 'sm'),
      item('stat-chats', 'sm'),
      item('stat-longest-streak', 'sm'),
      item('stat-current-streak', 'sm'),
      item('activity-heatmap', 'lg'),
      item('bench-results', 'lg')
    ]
  }
}

/** Full Dashboard Overview seed: every overview catalog widget. */
export function createDefaultOverviewLayout(): WidgetLayout {
  return {
    version: OVERVIEW_LAYOUT_VERSION,
    widgets: [
      item('usage-hero', 'lg'),
      item('stat-longest-agent', 'sm'),
      item('stat-chats', 'sm'),
      item('stat-longest-streak', 'sm'),
      item('stat-current-streak', 'sm'),
      item('activity-heatmap', 'lg'),
      item('stat-peak-day', 'sm'),
      item('stat-models-used', 'sm'),
      item('stat-messages', 'sm'),
      item('stat-tokens-in', 'sm'),
      item('stat-tokens-out', 'sm'),
      item('stat-cache-hit', 'sm'),
      item('stat-avg-tokens-chat', 'sm'),
      item('stat-files-size', 'sm'),
      item('models-chart', 'lg'),
      item('models-top-list', 'lg')
    ]
  }
}

export function normalizeLayout(
  layout: WidgetLayout | null | undefined,
  fallback: () => WidgetLayout
): WidgetLayout {
  if (!layout || !Array.isArray(layout.widgets) || layout.widgets.length === 0) {
    return fallback()
  }

  const widgets = layout.widgets
    .filter(widget => catalogEntry(widget.type))
    .map(widget => ({
      id: widget.id || crypto.randomUUID(),
      type: widget.type,
      size: widget.size || catalogEntry(widget.type)?.defaultSize || 'sm'
    }))

  if (widgets.length === 0) return fallback()

  return {
    version: Math.max(layout.version || 1, LAYOUT_VERSION),
    widgets
  }
}

/** Reseed Project Home when the stored seed version is older than the current default. */
export function normalizeProjectHomeLayout(
  layout: WidgetLayout | null | undefined
): WidgetLayout {
  if (
    !layout ||
    !Array.isArray(layout.widgets) ||
    layout.widgets.length === 0 ||
    (layout.version || 1) < LAYOUT_VERSION
  ) {
    return createDefaultProjectHomeLayout()
  }
  return normalizeLayout(layout, createDefaultProjectHomeLayout)
}

/** Reseed Overview when the stored seed version is older than the current default. */
export function normalizeOverviewLayout(
  layout: WidgetLayout | null | undefined
): WidgetLayout {
  if (
    !layout ||
    !Array.isArray(layout.widgets) ||
    layout.widgets.length === 0 ||
    (layout.version || 1) < OVERVIEW_LAYOUT_VERSION
  ) {
    return createDefaultOverviewLayout()
  }
  return normalizeLayout(layout, createDefaultOverviewLayout)
}
