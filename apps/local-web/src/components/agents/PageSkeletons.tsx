import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

/** Settings-style block — matches settings section body loaders. */
export function SettingsBlockSkeleton({
  className
}: {
  className?: string
}) {
  return (
    <div className={cn('space-y-3', className)} aria-busy="true">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-4 w-2/3" />
    </div>
  )
}

/** List row skeleton for Tools / Datasets / Models catalog rows. */
export function ListRowsSkeleton({
  rows = 6,
  withToggle = true,
  className
}: {
  rows?: number
  withToggle?: boolean
  className?: string
}) {
  return (
    <div className={cn('divide-y', className)} aria-busy="true">
      {Array.from({ length: rows }).map((_, index) => (
        <div
          key={index}
          className="flex items-start justify-between gap-3 px-4 py-3"
        >
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-[38%]" />
            <Skeleton className="h-3 w-[72%]" />
            <Skeleton className="h-3 w-[52%]" />
          </div>
          {withToggle ? (
            <Skeleton className="mt-0.5 h-4 w-8 shrink-0 rounded-full" />
          ) : (
            <Skeleton className="mt-0.5 h-8 w-16 shrink-0 rounded-md" />
          )}
        </div>
      ))}
    </div>
  )
}

/** Integration / skill card grid skeleton. */
export function CardGridSkeleton({
  cards = 6,
  columns = 2,
  className
}: {
  cards?: number
  columns?: 1 | 2 | 3
  className?: string
}) {
  return (
    <div
      className={cn(
        'grid gap-3',
        columns === 1 && 'grid-cols-1',
        columns === 2 && 'md:grid-cols-2',
        columns === 3 && 'md:grid-cols-2 xl:grid-cols-3',
        className
      )}
      aria-busy="true"
    >
      {Array.from({ length: cards }).map((_, index) => (
        <div
          key={index}
          className="bg-background/60 flex items-start justify-between gap-3 rounded-lg border p-3"
        >
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex items-center gap-2">
              <Skeleton className="size-6 shrink-0 rounded-md" />
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-3 w-14" />
            </div>
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-2/3" />
          </div>
          <Skeleton className="mt-0.5 h-4 w-8 shrink-0 rounded-full" />
        </div>
      ))}
    </div>
  )
}

/** Doctor diagnostics checklist skeleton. */
export function DoctorChecksSkeleton({
  groups = 3,
  rowsPerGroup = 4,
  className
}: {
  groups?: number
  rowsPerGroup?: number
  className?: string
}) {
  return (
    <div className={cn('space-y-5', className)} aria-busy="true">
      {Array.from({ length: groups }).map((_, groupIndex) => (
        <section key={groupIndex} className="space-y-2">
          <Skeleton className="h-3 w-24" />
          <div className="divide-y overflow-hidden rounded-xl border">
            {Array.from({ length: rowsPerGroup }).map((_, rowIndex) => (
              <div
                key={rowIndex}
                className="flex items-start gap-3 px-4 py-3"
              >
                <Skeleton className="mt-0.5 size-4 shrink-0 rounded-full" />
                <div className="min-w-0 flex-1 space-y-2">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-3/4" />
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

/**
 * Light chat hydration skeleton — same idea as fastfold-cloud-ui ChatSkeleton.
 */
export function ChatPageSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'mx-auto flex w-full max-w-[min(100%,_44rem)] flex-1 flex-col gap-6 px-4 pt-8',
        className
      )}
      aria-busy="true"
    >
      <div className="flex justify-end">
        <Skeleton className="h-7 w-[42%] rounded-xl" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-3 w-[34%]" />
        <Skeleton className="h-3 w-[90%]" />
        <Skeleton className="h-3 w-[76%]" />
        <Skeleton className="h-3 w-[58%]" />
      </div>
      <div className="flex justify-end">
        <Skeleton className="h-7 w-[32%] rounded-xl" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-3 w-[28%]" />
        <Skeleton className="h-3 w-[82%]" />
        <Skeleton className="h-3 w-[64%]" />
      </div>
    </div>
  )
}

/** Detail page body skeleton (skill / catalog detail) — matches detail page shell. */
export function DetailPageSkeleton({
  className,
  bare = false
}: {
  className?: string
  /** When true, skip ScrollArea + page padding (for use inside an existing shell). */
  bare?: boolean
}) {
  const body = (
    <div
      className={cn(
        bare ? 'mt-4 space-y-6' : 'mx-auto w-full max-w-3xl space-y-6 px-6 py-8 md:px-10',
        className
      )}
      aria-busy="true"
    >
      <div className="space-y-3">
        <Skeleton className="h-3 w-40" />
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-4 w-3/4" />
      </div>
      <div className="space-y-3">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-5/6" />
        <Skeleton className="h-3 w-2/3" />
      </div>
      <div className="space-y-3">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-10 w-full rounded-xl" />
        <Skeleton className="h-10 w-[75%] rounded-xl" />
      </div>
    </div>
  )
  if (bare) return body
  return <ScrollArea className="flex-1">{body}</ScrollArea>
}

/** Shared page title + subtitle placeholder. */
function PageHeaderSkeleton({
  titleWidth = 'w-36',
  subtitleWidth = 'w-[28rem]'
}: {
  titleWidth?: string
  subtitleWidth?: string
}) {
  return (
    <div className="mb-4 space-y-2">
      <Skeleton className={cn('h-8', titleWidth)} />
      <Skeleton className={cn('h-4 max-w-full', subtitleWidth)} />
    </div>
  )
}

/** Search bar row used by Tools / Skills / Integrations / Specialists. */
function SearchBarSkeleton({ withAction = false }: { withAction?: boolean }) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 pb-3 pt-2">
      <Skeleton className="h-11 min-w-[240px] max-w-3xl flex-1 rounded-md" />
      {withAction ? <Skeleton className="h-10 w-28 shrink-0 rounded-md" /> : null}
      <Skeleton className="size-9 shrink-0 rounded-md" />
    </div>
  )
}

/**
 * Settings-style dashboard pages:
 * General, Status, Agent Runtime, Storage, Environment.
 * Layout: `mx-auto max-w-3xl space-y-10 px-8 py-10`
 */
export function DashboardSettingsSkeleton({
  className,
  blocks = 3
}: {
  className?: string
  blocks?: number
}) {
  return (
    <ScrollArea className={cn('flex-1', className)}>
      <div
        className="mx-auto max-w-3xl space-y-10 px-8 py-10"
        aria-busy="true"
      >
        <PageHeaderSkeleton titleWidth="w-40" subtitleWidth="w-80" />
        {Array.from({ length: blocks }).map((_, index) => (
          <section key={index} className="space-y-3">
            <Skeleton className="h-3 w-28" />
            <div className="bg-background space-y-3 rounded-2xl border px-4 py-4">
              <SettingsBlockSkeleton />
            </div>
          </section>
        ))}
      </div>
    </ScrollArea>
  )
}

/**
 * Doctor page — settings column + check groups.
 * Layout: `mx-auto max-w-3xl … px-8 py-10`
 */
export function DashboardDoctorSkeleton({ className }: { className?: string }) {
  return (
    <ScrollArea className={cn('flex-1', className)}>
      <div
        className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-8 py-10"
        aria-busy="true"
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <PageHeaderSkeleton titleWidth="w-28" subtitleWidth="w-72" />
          <Skeleton className="h-9 w-24 shrink-0 rounded-md" />
        </div>
        <DoctorChecksSkeleton />
      </div>
    </ScrollArea>
  )
}

/**
 * Wide list/catalog pages: Models, Tools, Data, Skills, Integrations, MCP, Specialists.
 * Layout: `mx-auto max-w-7xl … p-4 md:p-6`
 */
export function DashboardListSkeleton({
  className,
  variant = 'list',
  withSidebar = false
}: {
  className?: string
  variant?: 'list' | 'cards' | 'models'
  withSidebar?: boolean
}) {
  return (
    <ScrollArea className={cn('flex-1', className)}>
      <div
        className={cn(
          'mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-6',
          withSidebar && 'xl:flex-row'
        )}
        aria-busy="true"
      >
        <div className="min-w-0 flex-1">
          <PageHeaderSkeleton />
          <SearchBarSkeleton withAction={variant !== 'models'} />
          {variant === 'cards' ? (
            <div className="space-y-4 pb-4">
              <section className="space-y-2">
                <Skeleton className="h-3 w-24" />
                <CardGridSkeleton cards={4} columns={2} />
              </section>
              <section className="space-y-2">
                <Skeleton className="h-3 w-16" />
                <ListRowsSkeleton rows={5} />
              </section>
            </div>
          ) : variant === 'models' ? (
            <div className="bg-muted/20 border-border/60 overflow-hidden rounded-xl border shadow-sm">
              <div className="flex items-center gap-2 border-b px-3 py-2">
                <Skeleton className="h-9 flex-1 rounded-md" />
                <Skeleton className="h-8 w-32 shrink-0 rounded-md" />
                <Skeleton className="h-8 w-28 shrink-0 rounded-md" />
                <Skeleton className="size-8 shrink-0 rounded-md" />
              </div>
              <ListRowsSkeleton rows={8} />
            </div>
          ) : (
            <div className="bg-muted/20 border-border/60 overflow-hidden rounded-xl border shadow-sm">
              <ListRowsSkeleton rows={8} />
            </div>
          )}
        </div>
        {withSidebar ? (
          <aside className="w-full shrink-0 space-y-3 xl:w-72">
            <Skeleton className="h-3 w-20" />
            <div className="space-y-2 rounded-xl border p-3">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-5/6" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          </aside>
        ) : null}
      </div>
    </ScrollArea>
  )
}

/**
 * Dashboard Overview — heatmap + featured sections.
 * Layout: `mx-auto max-w-5xl … px-6 py-8 sm:px-8 sm:py-10`
 */
export function DashboardOverviewSkeleton({
  className
}: {
  className?: string
}) {
  return (
    <ScrollArea className={cn('flex-1', className)}>
      <div
        className="mx-auto w-full max-w-5xl space-y-10 px-6 py-8 sm:px-8 sm:py-10"
        aria-busy="true"
      >
        <section className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <div className="grid grid-cols-12 gap-1 sm:grid-cols-[repeat(53,minmax(0,1fr))]">
            {Array.from({ length: 53 }).map((_, index) => (
              <Skeleton
                key={index}
                className="aspect-square w-full min-w-0 rounded-sm"
              />
            ))}
          </div>
        </section>
        <div className="space-y-10">
          <section className="space-y-3">
            <div className="flex items-end justify-between gap-2">
              <div className="space-y-1">
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-3 w-24" />
              </div>
              <Skeleton className="h-3 w-16" />
            </div>
            <CardGridSkeleton cards={2} columns={2} />
          </section>
          <section className="space-y-3">
            <div className="flex items-end justify-between gap-2">
              <div className="space-y-1">
                <Skeleton className="h-5 w-16" />
                <Skeleton className="h-3 w-20" />
              </div>
              <Skeleton className="h-3 w-16" />
            </div>
            <CardGridSkeleton cards={2} columns={2} />
          </section>
        </div>
      </div>
    </ScrollArea>
  )
}

/**
 * Home / project home — greeting column + recent cards.
 * Layout: `mx-auto max-w-5xl px-6 py-8 md:px-10`
 */
export function HomePageSkeleton({ className }: { className?: string }) {
  return (
    <ScrollArea className={cn('flex-1', className)}>
      <div
        className="mx-auto w-full max-w-5xl px-6 py-8 md:px-10"
        aria-busy="true"
      >
        <div className="mb-10 space-y-3">
          <Skeleton className="mx-auto size-12 rounded-2xl md:mx-0" />
          <Skeleton className="mx-auto h-8 w-64 md:mx-0" />
          <Skeleton className="mx-auto h-4 w-80 max-w-full md:mx-0" />
        </div>
        <section className="space-y-3">
          <Skeleton className="h-4 w-32" />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map((_, index) => (
              <div
                key={index}
                className="bg-background/60 space-y-3 rounded-xl border p-4"
              >
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            ))}
          </div>
        </section>
      </div>
    </ScrollArea>
  )
}

export type DashboardSkeletonKind =
  | 'overview'
  | 'settings'
  | 'doctor'
  | 'list'
  | 'cards'
  | 'models'
  | 'home'
  | 'detail'

/** Pick a dashboard Suspense fallback that matches the active route layout. */
export function DashboardPageSkeleton({
  kind,
  className
}: {
  kind: DashboardSkeletonKind
  className?: string
}) {
  switch (kind) {
    case 'overview':
      return <DashboardOverviewSkeleton className={className} />
    case 'settings':
      return <DashboardSettingsSkeleton className={className} />
    case 'doctor':
      return <DashboardDoctorSkeleton className={className} />
    case 'list':
      return <DashboardListSkeleton className={className} variant="list" />
    case 'cards':
      return (
        <DashboardListSkeleton
          className={className}
          variant="cards"
          withSidebar
        />
      )
    case 'models':
      return <DashboardListSkeleton className={className} variant="models" />
    case 'home':
      return <HomePageSkeleton className={className} />
    case 'detail':
    default:
      return <DetailPageSkeleton className={className} />
  }
}
