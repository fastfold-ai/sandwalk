import { Loader2 } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import type { DesktopCliPathStatus } from '@/lib/desktop'

function SettingsRow({
  label,
  description,
  children
}: {
  label: string
  description?: string
  children: ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-6 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{label}</p>
        {description ? (
          <p className="text-muted-foreground mt-0.5 text-xs leading-snug">
            {description}
          </p>
        ) : null}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

function cliStatusLabel(cli: DesktopCliPathStatus | null, busy: boolean): string {
  if (busy) return 'Checking CLI…'
  if (!cli) return 'CLI command'
  if (cli.version) return `CLI: ${cli.version}`
  switch (cli.state) {
    case 'ready':
      return 'CLI: sandwalk'
    case 'missing':
      return 'CLI: not installed'
    case 'foreign':
      return 'CLI: separate install'
    case 'unavailable':
      return 'CLI: unavailable'
    default:
      return 'CLI command'
  }
}

function cliActionLabel(
  cli: DesktopCliPathStatus | null,
  installing: boolean
): string {
  if (installing) return 'Installing…'
  if (!cli) return 'Install'
  if (cli.state === 'missing') return 'Install'
  if (cli.state === 'foreign') return 'Reinstall'
  return 'Reinstall'
}

export function GeneralViewVersionSection({
  sandwalkVersion,
  checkingUpdates,
  installingUpdate,
  hasChecked,
  upToDate,
  latestVersion,
  checkError,
  onCheckUpdates,
  onInstallUpdate,
  showCliPath,
  cliPath,
  checkingCliPath,
  installingCliPath,
  cliPathError,
  onCheckCliPath,
  onInstallCliPath
}: {
  sandwalkVersion: string
  checkingUpdates: boolean
  installingUpdate?: boolean
  hasChecked: boolean
  upToDate: boolean | null
  latestVersion: string | null
  checkError?: string | null
  onCheckUpdates: () => void
  onInstallUpdate?: () => void
  showCliPath?: boolean
  cliPath?: DesktopCliPathStatus | null
  checkingCliPath?: boolean
  installingCliPath?: boolean
  cliPathError?: string | null
  onCheckCliPath?: () => void
  onInstallCliPath?: () => void
}) {
  const busy = checkingUpdates || Boolean(installingUpdate)
  const available = upToDate === false && Boolean(latestVersion)
  const statusLabel = installingUpdate
    ? 'Installing update…'
    : checkingUpdates
      ? 'Checking for updates…'
      : checkError
        ? 'Could not check for updates'
        : available
          ? `Update available: ${latestVersion}`
          : hasChecked
            ? 'Desktop app is up to date'
            : 'Check for updates'
  const statusDescription = installingUpdate
    ? 'Downloading and installing. Sandwalk will relaunch when done.'
    : checkingUpdates
      ? 'Looking for a newer Sandwalk release…'
      : checkError
        ? checkError
        : available
          ? 'Update includes the desktop UI, agent server, and bundled CLI runtime.'
          : 'Sandwalk checks for new versions automatically. App updates refresh the nested server and CLI too.'
  const actionLabel = installingUpdate
    ? 'Installing…'
    : checkingUpdates
      ? 'Checking…'
      : available && onInstallUpdate
        ? 'Update now'
        : available
          ? 'Update available'
          : checkError
            ? 'Try again'
            : hasChecked
              ? 'Check again'
              : 'Check for updates'

  const cliBusy = Boolean(checkingCliPath || installingCliPath)
  const cliDescription =
    cliPathError ||
    cliPath?.message ||
    'Installs sandwalk into ~/.local/bin for Terminal access.'
  const canInstallCli =
    Boolean(onInstallCliPath) &&
    cliPath?.state !== 'unavailable' &&
    !cliBusy

  return (
    <section className="space-y-3">
      <h3 className="text-base font-semibold">Sandwalk</h3>

      <div className="divide-border/60 border-border/60 divide-y border-y">
        <SettingsRow label="Sandwalk App:">
          <code className="text-muted-foreground font-mono text-xs">
            {sandwalkVersion}
          </code>
        </SettingsRow>
        <SettingsRow label={statusLabel} description={statusDescription}>
          <Button
            type="button"
            variant={available && onInstallUpdate ? 'default' : 'outline'}
            size="sm"
            className="min-w-[8.5rem]"
            disabled={busy}
            onClick={() => {
              if (available && onInstallUpdate) {
                onInstallUpdate()
                return
              }
              onCheckUpdates()
            }}
          >
            {busy ? <Loader2 className="animate-spin" /> : null}
            {actionLabel}
          </Button>
        </SettingsRow>
        {showCliPath ? (
          <SettingsRow
            label={cliStatusLabel(cliPath ?? null, Boolean(checkingCliPath))}
            description={cliDescription}
          >
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="min-w-[5.5rem]"
                disabled={cliBusy || !onCheckCliPath}
                onClick={() => onCheckCliPath?.()}
              >
                {checkingCliPath ? <Loader2 className="animate-spin" /> : null}
                Check
              </Button>
              <Button
                type="button"
                variant={cliPath?.state === 'missing' ? 'default' : 'outline'}
                size="sm"
                className="min-w-[6.5rem]"
                disabled={!canInstallCli}
                onClick={() => onInstallCliPath?.()}
              >
                {installingCliPath ? (
                  <Loader2 className="animate-spin" />
                ) : null}
                {cliActionLabel(cliPath ?? null, Boolean(installingCliPath))}
              </Button>
            </div>
          </SettingsRow>
        ) : null}
      </div>
    </section>
  )
}
