import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

import {
  CardGridSkeleton,
  DetailPageSkeleton,
  DoctorChecksSkeleton,
  ListRowsSkeleton,
  PageHeaderSkeleton,
  SearchBarSkeleton,
  SettingsBlockSkeleton
} from './page-skeletons-blocks'

/**
 * Settings-style dashboard pages:
 * General, Status, Agent Runtime, Storage, Environment, Context, Sandbox.
 * Layout: `mx-auto max-w-7xl … px-4 pt-2 pb-4 md:px-6 md:pt-3 md:pb-6` (matches Skills).
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
        className="mx-auto w-full max-w-7xl space-y-10 px-4 pt-2 pb-4 md:px-6 md:pt-3 md:pb-6"
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
 * Layout: `mx-auto max-w-7xl … px-4 pt-2 pb-4 md:px-6 md:pt-3 md:pb-6` (matches Skills).
 */
export function DashboardDoctorSkeleton({ className }: { className?: string }) {
  return (
    <ScrollArea className={cn('flex-1', className)}>
      <div
        className="mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 pt-2 pb-4 md:px-6 md:pt-3 md:pb-6"
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
 * Layout: `mx-auto max-w-7xl … px-4 pt-2 pb-4 md:px-6 md:pt-3 md:pb-6`
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
          'mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 pt-2 pb-4 md:px-6 md:pt-3 md:pb-6',
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
 * Layout: `mx-auto max-w-7xl … px-4 pt-2 pb-4 md:px-6 md:pt-3 md:pb-6` (matches Skills).
 */
export function DashboardOverviewSkeleton({
  className
}: {
  className?: string
}) {
  return (
    <ScrollArea className={cn('flex-1', className)}>
      <div
        className="mx-auto w-full max-w-7xl space-y-10 px-4 pt-2 pb-4 md:px-6 md:pt-3 md:pb-6"
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
 * Layout: `mx-auto max-w-5xl px-6 pt-3 pb-8 md:px-10`
 */
export function HomePageSkeleton({ className }: { className?: string }) {
  return (
    <ScrollArea className={cn('flex-1', className)}>
      <div
        className="mx-auto w-full max-w-5xl px-6 pt-3 pb-8 md:px-10"
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
