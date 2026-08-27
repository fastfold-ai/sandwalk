import { ChevronDown, Monitor } from 'lucide-react'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import type { SttModelStatus } from '@/lib/desktop-voice'
import { cn } from '@/lib/utils'

const OPENAI_ICON = INTEGRATION_ICONS.openai

export function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KiB`
  return `${(bytes / (1024 * 1024)).toFixed(0)} MiB`
}

export function StatusBadge({
  tone,
  label
}: {
  tone: 'neutral' | 'ok' | 'warn' | 'bad'
  label: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[10px] font-medium',
        tone === 'neutral' && 'bg-muted text-muted-foreground',
        tone === 'ok' && 'bg-sky-500/12 text-sky-700 dark:text-sky-300',
        tone === 'warn' && 'bg-amber-500/12 text-amber-700 dark:text-amber-300',
        tone === 'bad' && 'bg-destructive/10 text-destructive'
      )}
    >
      <span
        className={cn(
          'size-1.5 shrink-0 rounded-full',
          tone === 'neutral' && 'bg-muted-foreground/50',
          tone === 'ok' && 'bg-sky-500',
          tone === 'warn' && 'bg-amber-500',
          tone === 'bad' && 'bg-destructive'
        )}
        aria-hidden
      />
      {label}
    </span>
  )
}

export function SttModelCard({
  model,
  active,
  supported,
  downloading,
  verifying,
  onInstall,
  onCancel,
  onRepair,
  onRemove,
  onUse
}: {
  model: SttModelStatus
  active: boolean
  supported: boolean
  downloading: boolean
  verifying: boolean
  onInstall: () => void
  onCancel: () => void
  onRepair: () => void
  onRemove: () => void
  onUse: () => void
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border px-3 py-3">
      <span className="bg-muted/50 grid size-9 shrink-0 place-items-center rounded-lg">
        {OPENAI_ICON ? (
          <img
            src={OPENAI_ICON.src}
            alt=""
            className={cn(
              'size-6 object-contain',
              OPENAI_ICON.invertInDark && 'dark:invert'
            )}
          />
        ) : (
          <Monitor className="size-4" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">
          {model.id === 'multi'
            ? 'Whisper Base · Multilingual'
            : 'Whisper Base · English'}
        </div>
        <div className="mt-0.5 flex min-w-0 flex-wrap items-center gap-1.5">
          {supported ? (
            <StatusBadge tone="ok" label="Supported" />
          ) : (
            <StatusBadge tone="bad" label="Unsupported" />
          )}
          {model.model_verified ? <StatusBadge tone="ok" label="Ready" /> : null}
          {active ? <StatusBadge tone="ok" label="In use" /> : null}
          <span className="text-muted-foreground truncate text-xs">
            OpenAI · local · {formatBytes(model.model_bytes)}
          </span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {model.model_verified && !active ? (
          <Button variant="outline" size="sm" onClick={onUse}>
            Use this
          </Button>
        ) : null}
        {model.model_verified ? (
          <div className="flex items-stretch">
            <Button
              variant="outline"
              size="sm"
              className="rounded-r-none border-r-0"
              onClick={onRepair}
            >
              Re-download
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-l-none px-2"
                  aria-label="More model actions"
                >
                  <ChevronDown className="size-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive"
                  onClick={onRemove}
                >
                  Remove
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        ) : downloading ? (
          <Button variant="outline" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        ) : verifying ? (
          <StatusBadge tone="warn" label="Checking…" />
        ) : (
          <Button size="sm" disabled={!supported} onClick={onInstall}>
            Install
          </Button>
        )}
      </div>
    </div>
  )
}
