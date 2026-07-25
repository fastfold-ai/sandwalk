import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

import {
  type EnvironmentConfirmState,
  mutationErrorMessage,
  normalizeName,
} from './environment-view-shared'

export function EnvironmentConfirmDialog({
  confirm,
  pending,
  onConfirmChange,
  onRunConfirmed,
}: {
  confirm: EnvironmentConfirmState | null
  pending: string | null
  onConfirmChange: (open: boolean) => void
  onRunConfirmed: () => Promise<void>
}) {
  return (
    <AlertDialog
      open={confirm !== null}
      onOpenChange={open => {
        if (!open) onConfirmChange(false)
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            {confirm?.action === 'uninstall'
              ? `Remove ${confirm.name}?`
              : `Install ${confirm?.name}?`}
          </AlertDialogTitle>
          <AlertDialogDescription>
            {confirm?.action === 'uninstall' ? (
              <>
                This uninstalls <code className="font-mono">{confirm.name}</code>{' '}
                from the sandbox Python environment.
              </>
            ) : confirm?.unlisted ? (
              <>
                <code className="font-mono">{confirm.name}</code> is not in the
                skill/tool catalog. It will still be installed into the agent
                sandbox. Core FastFold packages cannot be changed.
              </>
            ) : (
              <>
                Install <code className="font-mono">{confirm?.name}</code> into
                the sandbox Python environment. No server restart is required
                afterward in most cases.
              </>
            )}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending !== null}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction
            disabled={pending !== null}
            onClick={event => {
              event.preventDefault()
              void onRunConfirmed()
            }}
          >
            {confirm?.action === 'uninstall' ? 'Remove' : 'Install'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function useEnvironmentViewActions({
  onLoad,
  onInstall,
  onUninstall,
  catalogNames,
  setConfirm,
  setPending,
  setPackageName,
  setError: _setError,
}: {
  onLoad: (signal?: AbortSignal) => Promise<void>
  onInstall: (
    name: string,
    options?: { allowUnlisted?: boolean; signal?: AbortSignal },
  ) => Promise<{ message?: string }>
  onUninstall: (
    name: string,
    signal?: AbortSignal,
  ) => Promise<{ message?: string }>
  catalogNames: Set<string>
  setConfirm: (value: EnvironmentConfirmState | null) => void
  setPending: (value: string | null) => void
  setPackageName: (value: string) => void
  setError: (value: string | null) => void
}) {
  const requestInstall = (
    name: string,
    options: { fromCatalog: boolean },
  ) => {
    const trimmed = name.trim()
    if (!trimmed) return
    const unlisted = !catalogNames.has(normalizeName(trimmed))
    setConfirm({
      action: 'install',
      name: trimmed,
      allowUnlisted: options.fromCatalog ? false : true,
      unlisted: options.fromCatalog ? false : unlisted,
    })
  }

  const requestUninstall = (name: string) => {
    const trimmed = name.trim()
    if (!trimmed) return
    setConfirm({
      action: 'uninstall',
      name: trimmed,
      allowUnlisted: false,
      unlisted: false,
    })
  }

  const runConfirmed = async (confirm: EnvironmentConfirmState | null) => {
    if (!confirm) return
    const { action, name, allowUnlisted } = confirm
    setConfirm(null)
    setPending(name)
    try {
      const result =
        action === 'install'
          ? await onInstall(name, { allowUnlisted })
          : await onUninstall(name)
      const { toast } = await import('sonner')
      toast.success(result.message || `${action} ${name}`, {
        description:
          action === 'install'
            ? 'No server restart needed — new imports work in the next tool run.'
            : undefined,
      })
      if (action === 'install') setPackageName('')
      await onLoad()
    } catch (err) {
      const { toast } = await import('sonner')
      toast.error(mutationErrorMessage(err))
    } finally {
      setPending(null)
    }
  }

  return { requestInstall, requestUninstall, runConfirmed }
}
