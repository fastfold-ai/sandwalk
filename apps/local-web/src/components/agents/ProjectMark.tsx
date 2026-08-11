import {
  projectColorBgClass,
  projectColorTextClass,
  projectIconComponent
} from '@/lib/project-appearance'
import { cn } from '@/lib/utils'

export function ProjectMark({
  icon,
  color,
  className,
  iconClassName
}: {
  icon?: string | null
  color?: string | null
  className?: string
  iconClassName?: string
}) {
  const Icon = projectIconComponent(icon)
  return (
    <span
      className={cn(
        'inline-flex size-7 shrink-0 items-center justify-center rounded-md',
        projectColorBgClass(color),
        projectColorTextClass(color),
        className
      )}
    >
      <Icon className={cn('size-3.5', iconClassName)} />
    </span>
  )
}
