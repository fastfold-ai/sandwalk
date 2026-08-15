import { Check, Copy, Eye, EyeOff, Loader, Trash2 } from 'lucide-react'
import { type ReactNode,useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { copyText } from '@/lib/clipboard'
import { openInSystemBrowser } from '@/lib/desktop'
import { cn } from '@/lib/utils'

function setupHostLabel(url: string) {
  try {
    return new URL(url).hostname
  } catch {
    return 'provider site'
  }
}

/** Short secret preview matching Models / Integrations (`abcd…wxyz`). */
export function maskSecretPreview(value: string | null | undefined): string | null {
  const normalized = (value || '').trim()
  if (!normalized) return null
  if (normalized.length <= 8) return '••••••••'
  return `${normalized.slice(0, 4)}…${normalized.slice(-4)}`
}

export function McpApiKeyDialog({
  open,
  onOpenChange,
  title,
  description,
  icon,
  configured,
  maskedPreview,
  placeholderUnset,
  setupUrl,
  draft,
  onDraftChange,
  onRevealStored,
  onSave,
  onTest,
  onRemove
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: string | null
  icon?: ReactNode
  configured: boolean
  maskedPreview?: string | null
  placeholderUnset?: string | null
  setupUrl?: string | null
  draft: string
  onDraftChange: (value: string) => void
  onRevealStored?: () => Promise<string>
  onSave: () => Promise<{ ok: boolean; message: string } | void>
  onTest?: () => Promise<{ ok: boolean; message: string }>
  onRemove?: () => Promise<void>
}) {
  const [revealed, setRevealed] = useState(false)
  const [pendingAction, setPendingAction] = useState<
    'test' | 'save' | 'remove' | 'reveal' | 'copy' | null
  >(null)
  const [copied, setCopied] = useState(false)
  const [testResult, setTestResult] = useState<{
    ok: boolean
    message: string
  } | null>(null)
  const [resolvedPreview, setResolvedPreview] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setTestResult(null)
    setPendingAction(null)
    setCopied(false)
    setRevealed(false)
    setResolvedPreview((maskedPreview || '').trim() || null)
  }, [open, title, maskedPreview])

  // If catalog didn't send a preview yet, derive one from the stored secret.
  useEffect(() => {
    if (!open || !configured || !onRevealStored) return
    const fromProp = (maskedPreview || '').trim()
    if (fromProp || resolvedPreview) return
    let cancelled = false
    void (async () => {
      try {
        const value = (await onRevealStored()).trim()
        if (cancelled || !value) return
        setResolvedPreview(maskSecretPreview(value))
      } catch {
        // Keep the bullet fallback below.
      }
    })()
    return () => {
      cancelled = true
    }
  }, [open, configured, maskedPreview, onRevealStored, resolvedPreview])

  const busy = pendingAction !== null
  const canTest = Boolean(onTest && (configured || draft.trim()))
  const keyPreview =
    (maskedPreview || '').trim() || resolvedPreview || '••••••••'
  const inputPlaceholder = configured
    ? keyPreview
    : placeholderUnset || 'Enter your API key'

  const toggleReveal = async () => {
    if (revealed) {
      setRevealed(false)
      return
    }
    if (configured && !draft.trim() && onRevealStored) {
      setPendingAction('reveal')
      try {
        const value = (await onRevealStored()).trim()
        if (value) {
          onDraftChange(value)
          setResolvedPreview(maskSecretPreview(value))
        }
        setRevealed(true)
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : 'Unable to reveal saved key'
        )
      } finally {
        setPendingAction(null)
      }
      return
    }
    if (!draft.trim() && !configured) {
      toast.error('No API key to show')
      return
    }
    setRevealed(true)
  }

  const copySecret = async () => {
    let value = draft.trim()
    if (!value && configured && onRevealStored) {
      setPendingAction('copy')
      try {
        value = (await onRevealStored()).trim()
        if (value) {
          onDraftChange(value)
          setRevealed(true)
        }
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : 'Unable to copy saved key'
        )
        setPendingAction(null)
        return
      } finally {
        setPendingAction(null)
      }
    }
    if (!value) {
      toast.error('No API key to copy')
      return
    }
    const ok = await copyText(value)
    if (ok) {
      setCopied(true)
      toast.success('API key copied')
      window.setTimeout(() => setCopied(false), 1500)
    } else {
      toast.error('Could not copy — select the key manually')
    }
  }

  const runSave = async () => {
    setPendingAction('save')
    setTestResult(null)
    try {
      const result = await onSave()
      if (result) setTestResult(result)
    } catch (err) {
      setTestResult({
        ok: false,
        message: err instanceof Error ? err.message : 'Unable to save API key.'
      })
    } finally {
      setPendingAction(null)
    }
  }

  const runTest = async () => {
    if (!onTest) return
    setPendingAction('test')
    setTestResult(null)
    try {
      if (draft.trim()) {
        const result = await onSave()
        if (result) setTestResult(result)
        return
      }
      const result = await onTest()
      setTestResult(result)
    } catch (err) {
      setTestResult({
        ok: false,
        message: err instanceof Error ? err.message : 'Unable to test API key.'
      })
    } finally {
      setPendingAction(null)
    }
  }

  const runRemove = async () => {
    if (!onRemove) return
    setPendingAction('remove')
    setTestResult(null)
    try {
      await onRemove()
      onOpenChange(false)
    } catch (err) {
      setTestResult({
        ok: false,
        message:
          err instanceof Error ? err.message : 'Unable to remove API key.'
      })
    } finally {
      setPendingAction(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            {icon ? (
              <span className="bg-muted/50 grid size-9 place-items-center rounded-lg">
                {icon}
              </span>
            ) : null}
            <span className="min-w-0">
              <span className="block truncate">{title}</span>
              <span className="text-muted-foreground text-xs font-normal">
                {configured ? 'Secret saved' : 'Not set'}
              </span>
            </span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {description ? (
            <p className="text-muted-foreground text-sm leading-relaxed">
              {description}
            </p>
          ) : null}

          <div className="relative">
            <Input
              type={revealed ? 'text' : 'password'}
              value={draft}
              autoComplete="off"
              autoFocus
              onChange={event => onDraftChange(event.target.value)}
              placeholder={inputPlaceholder}
              className="bg-muted/40 pr-16 font-mono text-sm"
              onKeyDown={event => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  void runSave()
                }
              }}
            />
            <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center gap-0.5">
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground grid size-7 place-items-center rounded-md"
                aria-label="Copy API key"
                title="Copy API key"
                disabled={busy}
                onClick={() => void copySecret()}
              >
                {pendingAction === 'copy' ? (
                  <Loader className="size-4 animate-spin" />
                ) : copied ? (
                  <Check className="size-4 text-emerald-600 dark:text-emerald-400" />
                ) : (
                  <Copy className="size-4" />
                )}
              </button>
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground grid size-7 place-items-center rounded-md"
                aria-label={revealed ? 'Hide API key' : 'Show API key'}
                title={revealed ? 'Hide API key' : 'Show API key'}
                disabled={busy}
                onClick={() => void toggleReveal()}
              >
                {pendingAction === 'reveal' ? (
                  <Loader className="size-4 animate-spin" />
                ) : revealed ? (
                  <EyeOff className="size-4" />
                ) : (
                  <Eye className="size-4" />
                )}
              </button>
            </div>
          </div>

          {setupUrl ? (
            <p className="text-muted-foreground text-sm">
              No key yet?{' '}
              <button
                type="button"
                className="text-foreground underline underline-offset-2"
                onClick={() => void openInSystemBrowser(setupUrl)}
              >
                Create one at {setupHostLabel(setupUrl)} ↗
              </button>
            </p>
          ) : null}

          {testResult ? (
            <p
              className={cn(
                'rounded-md px-3 py-2 text-sm',
                testResult.ok
                  ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                  : 'bg-amber-500/15 text-amber-900 dark:text-amber-200'
              )}
            >
              {testResult.message}
            </p>
          ) : null}
        </div>

        <DialogFooter className="gap-2 sm:justify-between">
          <div className="flex flex-wrap gap-2">
            {configured && onRemove ? (
              <Button
                variant="ghost"
                className="text-destructive hover:text-destructive"
                disabled={busy}
                onClick={() => void runRemove()}
              >
                {pendingAction === 'remove' ? (
                  <Loader className="animate-spin" />
                ) : (
                  <Trash2 />
                )}
                Remove
              </Button>
            ) : null}
            {onTest ? (
              <Button
                variant="ghost"
                disabled={!canTest || busy}
                onClick={() => void runTest()}
              >
                {pendingAction === 'test' ? (
                  <Loader className="animate-spin" />
                ) : null}
                Test
              </Button>
            ) : null}
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              disabled={busy || !draft.trim()}
              onClick={() => void runSave()}
            >
              {pendingAction === 'save' ? (
                <Loader className="animate-spin" />
              ) : null}
              Save
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
