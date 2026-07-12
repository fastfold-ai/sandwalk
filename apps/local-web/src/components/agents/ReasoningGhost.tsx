import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger
} from '@/components/ui/accordion'
import { cn } from '@/lib/utils'

export function ReasoningGhost({
  id,
  label,
  thought,
  className
}: {
  id: string
  label: string
  thought: string
  className?: string
}) {
  if (!thought.trim()) return null
  return (
    <Accordion type="single" collapsible className={cn('w-full', className)}>
      <AccordionItem value={`reasoning-${id}`} className="border-none">
        <AccordionTrigger className="text-muted-foreground justify-start gap-1.5 px-0 py-1 text-xs font-normal hover:no-underline">
          <span>{label}</span>
        </AccordionTrigger>
        <AccordionContent className="px-0 pt-0.5">
          <p className="text-muted-foreground whitespace-pre-wrap text-xs italic">
            {thought}
          </p>
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}
