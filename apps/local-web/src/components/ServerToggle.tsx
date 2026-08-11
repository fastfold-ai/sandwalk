import { Check, ChevronUp, Server } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  DEFAULT_BACKEND_URL,
  isLocalBackendUrl,
  normalizeBackendUrl
} from '@/lib/backend-url'
import { cn } from '@/lib/utils'

const PORTAL_ATTR = 'data-sandwalk-server-toggle'

function serverLabel(url: string): string {
  if (isLocalBackendUrl(url)) return 'Local'
  try {
    const parsed = new URL(url)
    const host = parsed.hostname || 'Server'
    const port =
      parsed.port ||
      (parsed.protocol === 'https:'
        ? '443'
        : parsed.protocol === 'http:'
          ? '80'
          : '')
    return port && port !== '80' && port !== '443' ? `${host}:${port}` : host
  } catch {
    return 'Server'
  }
}

/**
 * Login server control — mirrors ThemeToggle, anchored bottom-left.
 */
export function ServerToggle({
  backendUrl,
  onChangeBackend,
  disabled = false
}: {
  backendUrl: string
  onChangeBackend: (url: string) => void | Promise<void>
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [draftUrl, setDraftUrl] = useState(backendUrl)
  const [busy, setBusy] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const isLocal = isLocalBackendUrl(backendUrl)
  const label = serverLabel(backendUrl)

  useEffect(() => {
    document.querySelectorAll(`[${PORTAL_ATTR}]`).forEach(node => node.remove())
    setMounted(true)
  }, [])

  useEffect(() => {
    setDraftUrl(backendUrl)
  }, [backendUrl])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    const onPointer = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onPointer)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('mousedown', onPointer)
    }
  }, [open])

  const apply = async (nextUrl: string) => {
    const normalized = normalizeBackendUrl(nextUrl)
    if (normalized === normalizeBackendUrl(backendUrl)) {
      setOpen(false)
      return
    }
    setBusy(true)
    try {
      await onChangeBackend(normalized)
      setOpen(false)
    } finally {
      setBusy(false)
    }
  }

  if (!mounted || typeof document === 'undefined') return null

  return createPortal(
    <div
      data-sandwalk-server-toggle="overlay"
      className="pointer-events-none fixed inset-0 z-[100]"
    >
      <div
        ref={rootRef}
        className="pointer-events-auto absolute bottom-6 left-6 flex w-[min(18rem,calc(100vw-3rem))] flex-col items-stretch gap-2"
      >
        {open ? (
          <div
            role="menu"
            aria-label="Agent server"
            className="bg-card w-full rounded-xl border p-1.5 shadow-xl"
          >
            <p className="text-muted-foreground px-2.5 py-1.5 text-[11px] font-medium tracking-[0.06em] uppercase">
              Agent server
            </p>

            <button
              type="button"
              role="menuitemradio"
              aria-checked={isLocal}
              disabled={busy || disabled}
              className="hover:bg-muted/60 flex w-full cursor-pointer items-start gap-2.5 rounded-lg border-0 bg-transparent px-2.5 py-2 text-left outline-none disabled:opacity-40"
              onClick={() => void apply(DEFAULT_BACKEND_URL)}
            >
              <Server className="text-muted-foreground mt-0.5 size-3.5 shrink-0" />
              <span className="min-w-0 flex-1">
                <span className="text-foreground block text-sm font-medium leading-tight">
                  Local
                </span>
                <span className="text-muted-foreground mt-0.5 block text-[11px] leading-snug">
                  {DEFAULT_BACKEND_URL}
                </span>
              </span>
              {isLocal ? (
                <Check className="text-foreground mt-0.5 size-3.5 shrink-0" />
              ) : (
                <span className="size-3.5 shrink-0" aria-hidden />
              )}
            </button>

            {!isLocal ? (
              <div className="hover:bg-muted/60 flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2">
                <Server className="text-muted-foreground mt-0.5 size-3.5 shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="text-foreground block text-sm font-medium leading-tight">
                    Current
                  </span>
                  <span
                    className="text-muted-foreground mt-0.5 block break-all text-[11px] leading-snug"
                    title={backendUrl}
                  >
                    {backendUrl}
                  </span>
                </span>
                <Check className="text-foreground mt-0.5 size-3.5 shrink-0" />
              </div>
            ) : null}

            <div className="bg-border my-1.5 h-px" aria-hidden />

            <div className="space-y-2 px-2.5 py-2">
              <label
                htmlFor="sandwalk-server-url"
                className="text-foreground block text-sm font-medium leading-tight"
              >
                Custom URL
              </label>
              <Input
                id="sandwalk-server-url"
                value={draftUrl}
                onChange={event => setDraftUrl(event.target.value)}
                placeholder="http://192.168.1.10:8787"
                spellCheck={false}
                autoComplete="url"
                disabled={busy || disabled}
                className="h-9 text-xs"
                onKeyDown={event => {
                  if (event.key === 'Enter') {
                    event.preventDefault()
                    void apply(draftUrl)
                  }
                }}
              />
              <p className="text-muted-foreground text-[11px] leading-snug">
                Switching clears this sign-in. Enter the new server’s API key if
                it requires auth.
              </p>
              <Button
                type="button"
                size="sm"
                className="w-full"
                disabled={busy || disabled || !draftUrl.trim()}
                onClick={() => void apply(draftUrl)}
              >
                {busy ? 'Switching…' : 'Use this server'}
              </Button>
            </div>
          </div>
        ) : null}

        <button
          type="button"
          aria-label={`Agent server: ${label}`}
          aria-expanded={open}
          aria-haspopup="menu"
          title={`Agent server: ${backendUrl}`}
          disabled={disabled}
          onClick={() => {
            setDraftUrl(backendUrl)
            setOpen(current => !current)
          }}
          className={cn(
            'text-muted-foreground hover:bg-muted/60 hover:text-foreground mr-auto inline-flex h-9 items-center gap-1.5 rounded-xl border-0 bg-transparent px-2.5 text-xs font-medium shadow-none transition-colors',
            disabled && 'pointer-events-none opacity-40'
          )}
        >
          <Server className="size-3.5 shrink-0" />
          <span className="max-w-[9rem] truncate">{label}</span>
          <ChevronUp
            className={cn(
              'size-3 shrink-0 opacity-60 transition-transform',
              open && 'rotate-180'
            )}
          />
        </button>
      </div>
    </div>,
    document.body
  )
}
