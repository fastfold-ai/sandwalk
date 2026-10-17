import { RotateCcw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { REMEMBERED_AUTH_STORAGE_KEY } from '@/lib/remembered-auth'

export function clearLocalAppPreferences() {
  const keep = new Set([REMEMBERED_AUTH_STORAGE_KEY])
  for (const key of Object.keys(localStorage)) {
    const sandwalkPref =
      key.startsWith('sandwalk') || key.startsWith('fastfold')
    if (sandwalkPref && !keep.has(key)) localStorage.removeItem(key)
  }
}

export function GeneralViewResetSection({
  resetting,
  onReset
}: {
  resetting: boolean
  onReset: () => void
}) {
  return (
    <section className="space-y-3">
      <h3 className="text-base font-semibold">Reset</h3>
      <div className="divide-border/60 border-border/60 divide-y border-y">
        <div className="flex items-center justify-between gap-6 py-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Reset Sandwalk</p>
            <p className="text-muted-foreground mt-0.5 text-xs leading-snug">
              Clears models, API keys, and app settings, then starts onboarding
              again. Chats stay on this machine.
            </p>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="min-w-[8.5rem]"
            disabled={resetting}
            onClick={onReset}
          >
            <RotateCcw />
            Reset
          </Button>
        </div>
      </div>
    </section>
  )
}
