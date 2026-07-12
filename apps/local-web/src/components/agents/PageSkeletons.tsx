import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

/** Settings-style block — matches fastfold-cloud-ui account/settings loaders. */
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
          className="bg-background/60 flex items-start justify-between gap-3 rounded-lg p-3"
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
          <div className="divide-y overflow-hidden">
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

/** Detail page body skeleton (skill detail, catalog detail). */
export function DetailPageSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('mt-4 space-y-6', className)} aria-busy="true">
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
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-[75%]" />
      </div>
    </div>
  )
}
