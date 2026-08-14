import { CircleAlert, Gift, Loader2 } from 'lucide-react'

import { useDesktopUpdate } from '@/hooks/useDesktopUpdate'
import type { DesktopUpdateProgress } from '@/lib/desktop-updater'
import { cn } from '@/lib/utils'

function progressLabel(progress: DesktopUpdateProgress | null): string {
  if (!progress) return 'Installing…'
  if (progress.phase === 'install') return 'Installing…'
  if (progress.total && progress.total > 0) {
    const pct = Math.min(100, Math.round((progress.received / progress.total) * 100))
    return `Downloading… ${pct}%`
  }
  return 'Downloading…'
}

export function DesktopUpdateBanner() {
  const update = useDesktopUpdate()
  const showFailure = Boolean(update.error) && !update.dismissed && !update.installing
  const showAvailable =
    update.available && !update.dismissed && !showFailure && !update.installing
  const showInstalling = update.installing
  if (!showFailure && !showAvailable && !showInstalling) return null

  const title = showInstalling
    ? progressLabel(update.progress)
    : showFailure
      ? 'Update failed'
      : 'New update available'
  const Icon = showInstalling ? Loader2 : showFailure ? CircleAlert : Gift

  return (
    <div
      className="bg-background mb-1 rounded-2xl px-3 py-2.5 shadow-[0_2px_8px_-2px_rgba(0,0,0,0.16)] dark:shadow-[0_8px_20px_-6px_rgba(0,0,0,0.28)]"
      data-testid="desktop-update-banner"
    >
      <div className="flex items-center gap-2">
        <Icon
          aria-hidden="true"
          className={cn('size-4 shrink-0', showInstalling && 'animate-spin')}
          strokeWidth={1.75}
        />
        <p className="min-w-0 flex-1 truncate text-sm font-medium">{title}</p>
      </div>
      {showInstalling &&
      update.progress?.total &&
      update.progress.total > 0 ? (
        <div className="bg-muted mt-2 h-1 overflow-hidden rounded-full">
          <div
            className="h-full rounded-full bg-[#3b6af5] transition-[width] duration-200"
            style={{
              width: `${Math.min(
                100,
                Math.round(
                  (update.progress.received / update.progress.total) * 100
                )
              )}%`
            }}
          />
        </div>
      ) : null}
      {showInstalling ? null : (
        <div className="mt-2 flex items-center justify-end gap-2">
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground px-1 py-0.5 text-sm"
            onClick={update.dismiss}
          >
            Later
          </button>
          <button
            type="button"
            className="rounded-md bg-[#3b6af5] px-2.5 py-1 text-sm font-medium text-white hover:bg-[#2f5de6]"
            onClick={() => void update.installUpdate()}
          >
            {showFailure ? 'Retry' : 'Install Now'}
          </button>
        </div>
      )}
    </div>
  )
}
