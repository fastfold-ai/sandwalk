import type { AgentModel } from '@sandwalk/agent-ui-core'
import { ChevronDown, Plus, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function ModelsCustomSection({
  open,
  customModels,
  onOpenChange,
  onOpenCustomCreate,
  onRemoveCustomModel
}: {
  open: boolean
  customModels: AgentModel[]
  onOpenChange: (open: boolean) => void
  onOpenCustomCreate: () => void
  onRemoveCustomModel: (model: AgentModel) => void
}) {
  return (
    <section className="space-y-3 border-t pt-6">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => onOpenChange(!open)}
      >
        <div className="min-w-0 pr-3">
          <h3 className="text-base font-semibold">Custom cloud models</h3>
          <p className="text-muted-foreground mt-1 text-sm">
            Add a provider model by name (for example an OpenAI deployment id)
            so it appears in the list above.
          </p>
        </div>
        <ChevronDown
          className={cn(
            'text-muted-foreground size-4 shrink-0 transition-transform',
            open && 'rotate-180'
          )}
        />
      </button>

      {open ? (
        <div className="space-y-3">
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-foreground"
            onClick={onOpenCustomCreate}
          >
            <Plus />
            Add Custom Model
          </Button>

          <div className="divide-y rounded-xl border">
            {customModels.length === 0 ? (
              <div className="text-muted-foreground px-4 py-6 text-sm">
                No custom cloud models yet.
              </div>
            ) : (
              customModels.map(model => (
                <div
                  key={model.id}
                  className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">
                      {model.label}
                    </div>
                    <div className="text-muted-foreground truncate font-mono text-xs">
                      {model.provider} · {model.id}
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8"
                    onClick={() => onRemoveCustomModel(model)}
                    aria-label={`Remove ${model.label}`}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}
    </section>
  )
}
