import { Check, Copy, Eye, EyeOff, Loader2 } from 'lucide-react'
import { useState, type KeyboardEvent } from 'react'
import { toast } from 'sonner'

import { Input } from '@/components/ui/input'
import { copyText } from '@/lib/clipboard'
import { cn } from '@/lib/utils'

export function McpApiKeyInput({
  value,
  onChange,
  placeholder,
  disabled = false,
  autoFocus = false,
  hasStoredKey = false,
  onRevealStored,
  className,
  onKeyDown
}: {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  disabled?: boolean
  autoFocus?: boolean
  /** True when a secret is already saved for this MCP. */
  hasStoredKey?: boolean
  /** Load the saved secret (Integrations) for show/copy. */
  onRevealStored?: () => Promise<string>
  className?: string
  onKeyDown?: (event: KeyboardEvent<HTMLInputElement>) => void
}) {
  const [revealed, setRevealed] = useState(false)
  const [busy, setBusy] = useState<'reveal' | 'copy' | null>(null)
  const [copied, setCopied] = useState(false)

  const ensureValue = async (): Promise<string> => {
    const draft = value.trim()
    if (draft) return draft
    if (!hasStoredKey || !onRevealStored) return ''
    setBusy(prev => prev || 'reveal')
    try {
      const stored = (await onRevealStored()).trim()
      if (stored) onChange(stored)
      return stored
    } finally {
      setBusy(null)
    }
  }

  const toggleReveal = async () => {
    if (revealed) {
      setRevealed(false)
      return
    }
    if (!value.trim() && hasStoredKey && onRevealStored) {
      setBusy('reveal')
      try {
        const stored = (await onRevealStored()).trim()
        if (!stored) {
          toast.error('No saved API key found')
          return
        }
        onChange(stored)
        setRevealed(true)
      } catch (err) {
        toast.error(
          err instanceof Error ? err.message : 'Unable to reveal saved key'
        )
      } finally {
        setBusy(null)
      }
      return
    }
    if (!value.trim() && !hasStoredKey) {
      toast.error('No API key to show')
      return
    }
    setRevealed(true)
  }

  const copySecret = async () => {
    setBusy('copy')
    try {
      const secret = await ensureValue()
      if (!secret) {
        toast.error('No API key to copy')
        return
      }
      setRevealed(true)
      const ok = await copyText(secret)
      if (ok) {
        setCopied(true)
        toast.success('API key copied')
        window.setTimeout(() => setCopied(false), 1500)
      } else {
        toast.error('Could not copy — select the key manually')
      }
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Unable to copy saved key'
      )
    } finally {
      setBusy(null)
    }
  }

  const showActions = Boolean(onRevealStored) || Boolean(value.trim())

  return (
    <div className={cn('relative max-w-md min-w-[12rem] flex-1', className)}>
      <Input
        type={revealed ? 'text' : 'password'}
        className={cn('font-mono text-sm', showActions && 'pr-16')}
        placeholder={
          placeholder ||
          (hasStoredKey
            ? 'Secret saved. Enter a new key to replace it.'
            : 'API key')
        }
        value={value}
        autoComplete="off"
        autoFocus={autoFocus}
        disabled={disabled || busy !== null}
        onChange={event => onChange(event.target.value)}
        onKeyDown={onKeyDown}
      />
      {showActions ? (
        <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center gap-0.5">
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground grid size-7 place-items-center rounded-md disabled:opacity-40"
            aria-label="Copy API key"
            title="Copy API key"
            disabled={disabled || busy !== null}
            onClick={() => void copySecret()}
          >
            {busy === 'copy' ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : copied ? (
              <Check className="size-3.5 text-emerald-600 dark:text-emerald-400" />
            ) : (
              <Copy className="size-3.5" />
            )}
          </button>
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground grid size-7 place-items-center rounded-md disabled:opacity-40"
            aria-label={revealed ? 'Hide API key' : 'Show API key'}
            title={revealed ? 'Hide API key' : 'Show API key'}
            disabled={disabled || busy !== null}
            onClick={() => void toggleReveal()}
          >
            {busy === 'reveal' ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : revealed ? (
              <EyeOff className="size-3.5" />
            ) : (
              <Eye className="size-3.5" />
            )}
          </button>
        </div>
      ) : null}
    </div>
  )
}
