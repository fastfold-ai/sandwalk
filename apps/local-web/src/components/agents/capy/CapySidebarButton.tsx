import capyLogo from '@/assets/capy-logo.png'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import { requestOpenCapy } from '@/lib/capy-ui'

export function CapySidebarButton() {
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="hover:bg-sidebar-accent/50 mb-1 flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left"
            onClick={() => requestOpenCapy()}
            data-capy-trigger
          >
            <img
              src={capyLogo}
              alt=""
              className="size-6 shrink-0 rounded-full object-cover"
            />
            <span className="min-w-0 flex-1 truncate text-sm font-medium">Capy</span>
            <span className="text-muted-foreground shrink-0 text-xs">Ctrl + Ctrl</span>
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" align="start">
          Open Capy
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
