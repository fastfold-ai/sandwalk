import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentProject,
  UsageOverview,
  WidgetLayout,
  WidgetLayoutItem,
  WidgetSize
} from '@sandwalk/agent-ui-core'
import {
  closestCenter,
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent
} from '@dnd-kit/core'
import {
  arrayMove,
  rectSortingStrategy,
  SortableContext,
  useSortable
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { createPortal } from 'react-dom'

import { HomeProjectBenchLinks } from '@/components/agents/home-project-bench-links'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import {
  cacheHitPercent,
  formatAgentDuration,
  formatStreakDays,
  formatTokenCount,
  peakDayLabel,
  type UsageGrain
} from '../usage-overview-utils'
import { catalogEntry } from './catalog'
import { CustomizeBoardBar } from './CustomizeBoardBar'
import {
  createDefaultOverviewLayout,
  createDefaultProjectHomeLayout
} from './defaults'
import { colSpanClass } from './grid'
import type { WidgetSurface, WidgetType } from './types'
import { useUsageOverview } from './useUsageOverview'
import { ActivityHeatmapWidget } from './widgets/ActivityHeatmapWidget'
import {
  MetricStatWidget,
  metricValueForType
} from './widgets/MetricStatWidget'
import { ModelsChartWidget } from './widgets/ModelsChartWidget'
import { ModelsTopListWidget } from './widgets/ModelsTopListWidget'
import { UsageHeroWidget } from './widgets/UsageHeroWidget'

type BoardClient = LocalAgentClient & {
  baseUrl?: string
  getUsageOverview?: (
    signalOrOpts?:
      | AbortSignal
      | { projectId?: string | null; signal?: AbortSignal }
  ) => Promise<UsageOverview>
}

type Formatters = Parameters<typeof metricValueForType>[2]

const SIZES: WidgetSize[] = ['sm', 'md', 'lg']

export function WidgetBoard({
  client,
  surface,
  layout,
  onLayoutChange,
  project,
  showAddBar = true
}: {
  client: BoardClient
  surface: WidgetSurface
  layout: WidgetLayout
  onLayoutChange: (layout: WidgetLayout) => void | Promise<void>
  project?: AgentProject | null
  /** When false, host the Add widget control outside the board (e.g. project header). */
  showAddBar?: boolean
}) {
  const projectId = surface === 'project' ? project?.id || null : null
  const { overview, error } = useUsageOverview(client, projectId)
  const [grain, setGrain] = useState<UsageGrain>('daily')
  const [busy, setBusy] = useState(false)
  const [activeId, setActiveId] = useState<string | null>(null)
  const [overlayWidth, setOverlayWidth] = useState<number | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } })
  )

  const presentTypes = useMemo(
    () => new Set(layout.widgets.map(item => item.type)),
    [layout.widgets]
  )
  const sortableIds = useMemo(
    () => layout.widgets.map(item => item.id),
    [layout.widgets]
  )
  const activeItem = useMemo(
    () => layout.widgets.find(item => item.id === activeId) || null,
    [activeId, layout.widgets]
  )

  const persist = async (next: WidgetLayout) => {
    setBusy(true)
    try {
      await onLayoutChange(next)
    } finally {
      setBusy(false)
    }
  }

  const updateItem = (id: string, patch: Partial<WidgetLayoutItem>) => {
    void persist({
      ...layout,
      widgets: layout.widgets.map(item =>
        item.id === id ? { ...item, ...patch } : item
      )
    })
  }

  const removeItem = (id: string) => {
    void persist({
      ...layout,
      widgets: layout.widgets.filter(item => item.id !== id)
    })
  }

  const addItem = (type: WidgetType) => {
    const entry = catalogEntry(type)
    if (!entry) return
    void persist({
      ...layout,
      widgets: [
        ...layout.widgets,
        {
          id: crypto.randomUUID(),
          type,
          size: entry.defaultSize
        }
      ]
    })
  }

  const resetLayout = () => {
    void persist(
      surface === 'project'
        ? createDefaultProjectHomeLayout()
        : createDefaultOverviewLayout()
    )
  }

  const clearDrag = () => {
    setActiveId(null)
    setOverlayWidth(null)
  }

  const onDragStart = (event: DragStartEvent) => {
    setActiveId(String(event.active.id))
    const width = event.active.rect.current.initial?.width
    setOverlayWidth(typeof width === 'number' ? width : null)
  }

  const onDragEnd = (event: DragEndEvent) => {
    const draggingId = String(event.active.id)
    const overId = event.over ? String(event.over.id) : null
    clearDrag()
    if (!overId || draggingId === overId) return
    const from = layout.widgets.findIndex(item => item.id === draggingId)
    const to = layout.widgets.findIndex(item => item.id === overId)
    if (from < 0 || to < 0) return
    void persist({
      ...layout,
      widgets: arrayMove(layout.widgets, from, to)
    })
  }

  const formatters: Formatters = {
    formatTokenCount,
    formatAgentDuration,
    formatStreakDays,
    peakDayLabel,
    cacheHitPercent
  }

  return (
    <div className={cn(busy && 'pointer-events-none opacity-80')}>
      {showAddBar ? (
        <CustomizeBoardBar
          surface={surface}
          presentTypes={presentTypes}
          onAdd={addItem}
          onReset={resetLayout}
        />
      ) : null}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onDragCancel={clearDrag}
      >
        <SortableContext items={sortableIds} strategy={rectSortingStrategy}>
          <div className="grid grid-cols-12 gap-3">
            {layout.widgets.map(item => (
              <SortableWidget
                key={item.id}
                item={item}
                overview={overview}
                error={error}
                grain={grain}
                onGrainChange={setGrain}
                client={client}
                project={project}
                formatters={formatters}
                surface={surface}
                onSizeChange={size => updateItem(item.id, { size })}
                onRemove={() => removeItem(item.id)}
              />
            ))}
          </div>
        </SortableContext>
        {typeof document !== 'undefined'
          ? createPortal(
              <DragOverlay dropAnimation={null}>
                {activeItem ? (
                  <div
                    className="cursor-grabbing rounded-xl shadow-2xl"
                    style={{
                      width: overlayWidth ?? undefined,
                      maxWidth: 'min(100vw - 2rem, 56rem)'
                    }}
                  >
                    <WidgetBody
                      item={activeItem}
                      overview={overview}
                      error={error}
                      grain={grain}
                      onGrainChange={setGrain}
                      client={client}
                      project={project}
                            formatters={formatters}
                      surface={surface}
                    />
                  </div>
                ) : null}
              </DragOverlay>,
              document.body
            )
          : null}
      </DndContext>
    </div>
  )
}

function SortableWidget({
  item,
  overview,
  error,
  grain,
  onGrainChange,
  client,
  project,
  formatters,
  surface,
  onSizeChange,
  onRemove
}: {
  item: WidgetLayoutItem
  overview: UsageOverview | null
  error: string | null
  grain: UsageGrain
  onGrainChange: (grain: UsageGrain) => void
  client: BoardClient
  project?: AgentProject | null
  formatters: Formatters
  surface: WidgetSurface
  onSizeChange: (size: WidgetSize) => void
  onRemove: () => void
}) {
  const entry = catalogEntry(item.type)
  const allowed = entry?.allowedSizes || SIZES
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: item.id })

  return (
    <div
      ref={setNodeRef}
      style={{
        // Translate only — Transform's scaleX/Y is what "zooms" mixed-span grid cards.
        transform: CSS.Translate.toString(transform),
        transition,
        opacity: isDragging ? 0.35 : undefined
      }}
      className={cn(
        'group relative',
        colSpanClass(item.size),
        // SM stays compact; MD/LG stretch so neighbors in a row match height.
        item.size === 'sm' ? 'self-start' : 'h-full'
      )}
    >
      <div
        className={cn(
          'pointer-events-none absolute top-2 right-2 z-10 flex items-center gap-0.5 opacity-0 transition-opacity',
          'group-hover:pointer-events-auto group-hover:opacity-100',
          'group-focus-within:pointer-events-auto group-focus-within:opacity-100',
          isDragging && 'opacity-0'
        )}
      >
        <button
          type="button"
          className="bg-background/95 text-muted-foreground hover:text-foreground flex size-6 cursor-grab items-center justify-center rounded-md border shadow-sm active:cursor-grabbing"
          aria-label="Drag to reorder"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="size-3" />
        </button>
        <div className="bg-background/95 flex rounded-md border p-0.5 text-[10px] shadow-sm">
          {SIZES.map(size => (
            <button
              key={size}
              type="button"
              disabled={!allowed.includes(size)}
              className={cn(
                'rounded px-1.5 py-0.5 uppercase',
                item.size === size
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:text-foreground',
                !allowed.includes(size) && 'opacity-30'
              )}
              onClick={() => onSizeChange(size)}
            >
              {size}
            </button>
          ))}
        </div>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="bg-background/95 size-6 border text-red-600 shadow-sm"
          onClick={onRemove}
          aria-label="Remove widget"
        >
          <X className="size-3" />
        </Button>
      </div>
      <WidgetBody
        item={item}
        overview={overview}
        error={error}
        grain={grain}
        onGrainChange={onGrainChange}
        client={client}
        project={project}
        formatters={formatters}
        surface={surface}
      />
    </div>
  )
}

function WidgetBody({
  item,
  overview,
  error,
  grain,
  onGrainChange,
  client,
  project,
  formatters,
  surface
}: {
  item: WidgetLayoutItem
  overview: UsageOverview | null
  error: string | null
  grain: UsageGrain
  onGrainChange: (grain: UsageGrain) => void
  client: BoardClient
  project?: AgentProject | null
  formatters: Formatters
  surface: WidgetSurface
}) {
  if (item.type === 'usage-hero') {
    return (
      <UsageHeroWidget
        overview={overview}
        error={error}
        size={item.size}
        scopeLabel={surface === 'project' ? 'this project' : undefined}
      />
    )
  }
  if (item.type === 'activity-heatmap') {
    return (
      <ActivityHeatmapWidget
        overview={overview}
        size={item.size}
        grain={grain}
        onGrainChange={onGrainChange}
      />
    )
  }
  if (item.type === 'models-chart') {
    return (
      <ModelsChartWidget
        overview={overview}
        error={error}
        size={item.size}
      />
    )
  }
  if (item.type === 'models-top-list') {
    return (
      <ModelsTopListWidget
        overview={overview}
        error={error}
        size={item.size}
      />
    )
  }
  if (item.type === 'bench-results' && project) {
    return (
      <HomeProjectBenchLinks
        client={client}
        projectId={project.id}
        embedded
      />
    )
  }
  const metric = metricValueForType(item.type, overview, formatters)
  if (metric) {
    return (
      <MetricStatWidget
        label={metric.label}
        value={metric.value}
        size={item.size}
        loading={!overview && !error}
      />
    )
  }
  return null
}
