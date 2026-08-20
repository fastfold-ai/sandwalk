import { Loader } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'

import { CLOUD_PROVIDERS } from './models-view-utils'

export function ModelsCustomDialog({
  open,
  customForm,
  savingCustom,
  onOpenChange,
  onCustomFormChange,
  onSaveCustomModel
}: {
  open: boolean
  customForm: { provider: string; id: string; label: string }
  savingCustom: boolean
  onOpenChange: (open: boolean) => void
  onCustomFormChange: (
    value:
      | { provider: string; id: string; label: string }
      | ((
          prev: { provider: string; id: string; label: string }
        ) => { provider: string; id: string; label: string })
  ) => void
  onSaveCustomModel: () => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Custom Model</DialogTitle>
        </DialogHeader>
        <div className="grid gap-3">
          <label className="space-y-1.5 text-sm">
            <span className="text-muted-foreground text-xs">Provider</span>
            <select
              className="border-input bg-background h-9 w-full rounded-md border px-3 text-sm"
              value={customForm.provider}
              onChange={event =>
                onCustomFormChange(prev => ({
                  ...prev,
                  provider: event.target.value
                }))
              }
            >
              {CLOUD_PROVIDERS.map(option => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1.5 text-sm">
            <span className="text-muted-foreground text-xs">Model name</span>
            <Input
              value={customForm.id}
              onChange={event =>
                onCustomFormChange(prev => ({ ...prev, id: event.target.value }))
              }
              placeholder={
                customForm.provider === 'anthropic'
                  ? 'claude-sonnet-4-20250514'
                  : 'gpt-4.1-mini'
              }
              className="font-mono text-sm"
            />
          </label>
          <label className="space-y-1.5 text-sm">
            <span className="text-muted-foreground text-xs">
              Display label (optional)
            </span>
            <Input
              value={customForm.label}
              onChange={event =>
                onCustomFormChange(prev => ({
                  ...prev,
                  label: event.target.value
                }))
              }
              placeholder="Friendly name in the model list"
            />
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            disabled={savingCustom || !customForm.id.trim()}
            onClick={onSaveCustomModel}
          >
            {savingCustom ? <Loader className="animate-spin" /> : null}
            Add to list
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
