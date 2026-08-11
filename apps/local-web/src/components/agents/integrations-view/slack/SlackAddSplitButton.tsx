import { Cable, ChevronDown, ExternalLink, Loader2, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'

const FASTFOLD_CLOUD_PATH = '/dashboard/integrations/fastfold-cloud'
const FASTFOLD_ICON = INTEGRATION_ICONS['fastfold-cloud']

function needsFastfoldAccount(error: string | null) {
  if (!error) return false
  const text = error.toLowerCase()
  return (
    text.includes('fastfold') ||
    text.includes('api key') ||
    text.includes('one-click')
  )
}

export function SlackAddSplitButton({
  busy,
  waiting,
  onAddToSlack,
  onOpenManual
}: {
  busy: boolean
  waiting?: boolean
  onAddToSlack: () => void
  onOpenManual: () => void
}) {
  return (
    <div className="inline-flex items-stretch">
      <Button
        size="sm"
        className="h-8 gap-1.5 rounded-r-none"
        disabled={busy || waiting}
        onClick={onAddToSlack}
      >
        {waiting ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <Plus className="size-3.5" />
        )}
        Add
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            size="sm"
            className="h-8 rounded-l-none border-l border-l-black/10 px-2 dark:border-l-white/15"
            disabled={busy || waiting}
            aria-label="More add options"
          >
            <ChevronDown className="size-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuItem onSelect={onOpenManual}>
            Add via Socket (manual)
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

export function SlackOneClickDialog({
  open,
  busy,
  waiting,
  error,
  onOpenChange,
  onRetry,
  onOpenManual
}: {
  open: boolean
  busy: boolean
  waiting: boolean
  error: string | null
  onOpenChange: (open: boolean) => void
  onRetry: () => void
  onOpenManual: () => void
}) {
  const missingAccount = needsFastfoldAccount(error)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader className="text-left">
          <DialogTitle className="text-base">Add to Slack</DialogTitle>
          <DialogDescription className="text-[12px]">
            {missingAccount
              ? 'One-click relay needs a Fastfold account. Or connect with Socket Mode instead.'
              : 'Approve Sandwalk for your workspace in the browser — no tokens to copy.'}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {missingAccount ? (
            <div className="space-y-2">
              <Link
                to={FASTFOLD_CLOUD_PATH}
                onClick={() => onOpenChange(false)}
                className="border-border/70 hover:bg-muted/40 flex items-center gap-3 rounded-lg border px-3 py-3 transition-colors"
              >
                <img
                  src={FASTFOLD_ICON.src}
                  alt=""
                  className="size-5 object-contain"
                />
                <div className="min-w-0 text-left">
                  <p className="text-foreground text-[13px] font-medium">
                    Add Fastfold account
                  </p>
                  <p className="text-muted-foreground text-[11px]">
                    Save your Fastfold API key, then try Add again.
                  </p>
                </div>
              </Link>
              <button
                type="button"
                className="border-border/70 hover:bg-muted/40 flex w-full items-center gap-3 rounded-lg border px-3 py-3 text-left transition-colors"
                onClick={() => {
                  onOpenChange(false)
                  onOpenManual()
                }}
              >
                <Cable className="text-muted-foreground size-5 shrink-0" />
                <div className="min-w-0">
                  <p className="text-foreground text-[13px] font-medium">
                    Manual Socket
                  </p>
                  <p className="text-muted-foreground text-[11px]">
                    Connect with app tokens — no Fastfold account needed.
                  </p>
                </div>
              </button>
            </div>
          ) : null}

          {error && !missingAccount ? (
            <div className="border-destructive/40 bg-destructive/5 rounded-lg border p-3">
              <p className="text-[12px] leading-relaxed">{error}</p>
              <Button
                size="sm"
                variant="outline"
                className="mt-3 h-8"
                onClick={() => {
                  onOpenChange(false)
                  onOpenManual()
                }}
              >
                Manual Socket
              </Button>
            </div>
          ) : null}

          {waiting ? (
            <div className="border-border/70 bg-muted/30 flex items-center gap-2 rounded-lg border p-3">
              <Loader2 className="size-3.5 shrink-0 animate-spin" />
              <p className="text-[12px] leading-relaxed">
                Waiting for you to approve Sandwalk in Slack…
              </p>
            </div>
          ) : null}

          {!waiting && !error ? (
            <Button
              size="sm"
              className="h-8"
              disabled={busy}
              onClick={onRetry}
            >
              Add to Slack
              <ExternalLink className="ml-1.5 size-3.5" />
            </Button>
          ) : null}

          {waiting || error ? (
            <Button
              size="sm"
              variant="ghost"
              className="h-8"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  )
}
