import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { cn } from '@/lib/utils'

export function ModalGlyph({ className }: { className?: string }) {
  const icon = INTEGRATION_ICONS.modal
  return (
    <img
      src={icon.src}
      alt=""
      className={cn('size-3.5 shrink-0 rounded-sm object-contain', className)}
    />
  )
}
