import { Skeleton } from '@/components/ui/skeleton'

export function UsageHeroSkeleton() {
  return (
    <div className="mt-6 space-y-6" aria-busy="true" aria-label="Loading usage">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="space-y-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-6 w-16" />
          </div>
        ))}
      </div>
      <div className="space-y-2">
        <div className="grid grid-cols-[repeat(53,minmax(0,1fr))] gap-1">
          {Array.from({ length: 53 }).map((_, index) => (
            <Skeleton
              key={index}
              className="aspect-square w-full min-w-0 rounded-sm"
            />
          ))}
        </div>
        <Skeleton className="h-3 w-40" />
      </div>
      <div className="space-y-3">
        <Skeleton className="h-3 w-16" />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="space-y-2">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-5 w-20" />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function UsageModelsSkeleton() {
  return (
    <div
      className="mt-6 space-y-8"
      aria-busy="true"
      aria-label="Loading model usage"
    >
      <Skeleton className="h-48 w-full rounded-lg" />
      <div className="space-y-3">
        <Skeleton className="h-3 w-28" />
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-4 w-12" />
            </div>
            <Skeleton className="h-1.5 w-full rounded-full" />
            <Skeleton className="h-3 w-32" />
          </div>
        ))}
      </div>
    </div>
  )
}
