import { ChevronDown, Monitor, Volume2 } from 'lucide-react'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import type { SttModelStatus, TtsModelStatus } from '@/lib/desktop-voice'
import { cn } from '@/lib/utils'

const OPENAI_ICON = INTEGRATION_ICONS.openai

const compactBtn =
  'h-6 gap-1 px-2 text-[11px] [&_svg]:size-3'

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
  onUse?: () => void
}) {
  return (
    <div className="hover:bg-muted/40 flex h-full items-start gap-2 rounded-xl border px-3 py-3 transition-colors">
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
          Whisper Base · Multilingual
        </div>
        <p className="text-muted-foreground mt-0.5 truncate text-xs">
          OpenAI · local · {formatBytes(model.model_bytes)}
        </p>
      </div>
      <VoiceCardActions
        verified={model.model_verified}
        active={active}
        supported={supported}
        downloading={downloading}
        verifying={verifying}
        moreLabel="More model actions"
        onUse={onUse}
        onInstall={onInstall}
        onCancel={onCancel}
        onRepair={onRepair}
        onRemove={onRemove}
      />
    </div>
  )
}

export function TtsQualityCard({
  model,
  active,
  supported,
  downloading,
  onInstall,
  onCancel,
  onRepair,
  onRemove,
  onUse
}: {
  model: TtsModelStatus
  active: boolean
  supported: boolean
  downloading: boolean
  onInstall: () => void
  onCancel: () => void
  onRepair: () => void
  onRemove: () => void
  onUse: () => void
}) {
  return (
    <div className="hover:bg-muted/40 flex h-full items-start gap-2 rounded-xl border px-3 py-3 transition-colors">
      <span className="bg-muted/50 grid size-9 shrink-0 place-items-center rounded-lg">
        <Volume2 className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{model.name}</div>
        <p className="text-muted-foreground mt-0.5 line-clamp-2 text-xs">
          {model.quality} · {formatBytes(model.model_bytes)}
        </p>
      </div>
      <VoiceCardActions
        verified={model.model_verified}
        active={active}
        supported={supported}
        downloading={downloading}
        moreLabel="More Capy voice actions"
        onUse={onUse}
        onInstall={onInstall}
        onCancel={onCancel}
        onRepair={onRepair}
        onRemove={onRemove}
      />
    </div>
  )
}

function VoiceCardActions({
  verified,
  active,
  supported,
  downloading,
  verifying,
  moreLabel,
  onUse,
  onInstall,
  onCancel,
  onRepair,
  onRemove
}: {
  verified: boolean
  active: boolean
  supported: boolean
  downloading: boolean
  verifying?: boolean
  moreLabel: string
  onUse?: () => void
  onInstall: () => void
  onCancel: () => void
  onRepair: () => void
  onRemove: () => void
}) {
  return (
    <div className="flex shrink-0 flex-wrap items-start justify-end gap-1">
      {onUse && verified && !active ? (
        <Button
          variant="outline"
          size="sm"
          className={compactBtn}
          onClick={onUse}
        >
          Use this
        </Button>
      ) : null}
      {verified ? (
        <div className="flex items-stretch">
          <Button
            variant="outline"
            size="sm"
            className={cn(compactBtn, 'rounded-r-none border-r-0')}
            onClick={onRepair}
          >
            Re-download
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className={cn(compactBtn, 'rounded-l-none px-1.5')}
                aria-label={moreLabel}
              >
                <ChevronDown />
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
        <Button
          variant="outline"
          size="sm"
          className={compactBtn}
          onClick={onCancel}
        >
          Cancel
        </Button>
      ) : verifying ? (
        <StatusBadge tone="warn" label="Checking…" />
      ) : (
        <Button
          size="sm"
          className={compactBtn}
          disabled={!supported}
          onClick={onInstall}
        >
          Install
        </Button>
      )}
    </div>
  )
}
