import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { ExternalLink, Loader, Plus } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { openInSystemBrowser } from '@/lib/desktop'

import { FASTFOLD_ADD_HEADER_SLOT_ID } from '../integrations-view-detail-header'

const ONE_CLICK_TIMEOUT_MS = 5 * 60 * 1000
const ONE_CLICK_POLL_MS = 2000

export function FastfoldAddControls({
  client,
  configured,
  onImported,
  placement = 'portal'
}: {
  client: LocalAgentClient
  configured: boolean
  onImported: () => void | Promise<void>
  /** portal = Integrations header slot; inline = render button in place (onboarding). */
  placement?: 'portal' | 'inline'
}) {
  const [headerSlot, setHeaderSlot] = useState<Element | null>(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [waiting, setWaiting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const cancelledRef = useRef(false)

  useEffect(() => {
    if (placement !== 'portal') {
      setHeaderSlot(null)
      return
    }
    setHeaderSlot(document.getElementById(FASTFOLD_ADD_HEADER_SLOT_ID))
  }, [placement])

  useEffect(() => {
    if (open) return
    cancelledRef.current = true
    setWaiting(false)
    setBusy(false)
    setError(null)
  }, [open])

  const start = async () => {
    cancelledRef.current = false
    setBusy(true)
    setError(null)
    setWaiting(false)
    setOpen(true)
    try {
      const { authUrl } = await client.startFastfoldOneClick()
      if (cancelledRef.current) return
      openInSystemBrowser(authUrl)
      setBusy(false)
      setWaiting(true)
      const deadline = Date.now() + ONE_CLICK_TIMEOUT_MS
      while (Date.now() < deadline) {
        await new Promise(resolve => window.setTimeout(resolve, ONE_CLICK_POLL_MS))
        if (cancelledRef.current) return
        try {
          const result = await client.importFastfoldOneClick()
          if (result.ready) {
            setWaiting(false)
            setOpen(false)
            toast.success('Fastfold AI Cloud connected.')
            await onImported()
            return
          }
        } catch (cause) {
          // Keep polling while the user is still on the allow page.
          const message =
            cause instanceof Error ? cause.message : 'Unable to import API key.'
          if (
            message.toLowerCase().includes('denied') ||
            message.toLowerCase().includes('no sandwalk allow')
          ) {
            setWaiting(false)
            setError(message)
            return
          }
        }
      }
      setWaiting(false)
      setError(
        'No key arrived. Finish Allow in the browser and try Add again.'
      )
    } catch (cause) {
      setBusy(false)
      setWaiting(false)
      setError(
        cause instanceof Error
          ? cause.message
          : 'Unable to start Fastfold allow flow.'
      )
    }
  }

  const addButton = (
    <Button
      size="sm"
      className="h-8 gap-1.5"
      disabled={busy || waiting}
      onClick={() => void start()}
    >
      {busy || waiting ? (
        <Loader className="size-3.5 animate-spin" />
      ) : (
        <Plus className="size-3.5" />
      )}
      {configured ? 'Update' : 'Add'}
    </Button>
  )

  return (
    <>
      {placement === 'inline' ? addButton : null}
      {placement === 'portal' && headerSlot != null
        ? createPortal(addButton, headerSlot)
        : null}
      <Dialog
        open={open}
        onOpenChange={next => {
          if (!next) cancelledRef.current = true
          setOpen(next)
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader className="text-left">
            <DialogTitle className="text-base">
              {configured ? 'Update Fastfold account' : 'Add Fastfold account'}
            </DialogTitle>
            <DialogDescription className="text-[12px]">
              Approve Sandwalk in your browser — pick Personal or a Team, then
              Allow. We&apos;ll import the API key automatically.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {error ? (
              <div className="border-destructive/40 bg-destructive/5 rounded-lg border p-3">
                <p className="text-[12px] leading-relaxed">{error}</p>
                <Button
                  size="sm"
                  className="mt-3 h-8"
                  onClick={() => void start()}
                >
                  Try again
                  <ExternalLink className="ml-1.5 size-3.5" />
                </Button>
              </div>
            ) : null}
            {waiting ? (
              <div className="border-border/70 bg-muted/30 flex items-center gap-2 rounded-lg border p-3">
                <Loader className="size-3.5 shrink-0 animate-spin" />
                <p className="text-[12px] leading-relaxed">
                  Waiting for you to Allow Sandwalk in Fastfold Cloud…
                </p>
              </div>
            ) : null}
            {!waiting && !error ? (
              <div className="border-border/70 bg-muted/30 flex items-center gap-2 rounded-lg border p-3">
                <Loader className="size-3.5 shrink-0 animate-spin" />
                <p className="text-[12px] leading-relaxed">
                  Opening Fastfold Cloud…
                </p>
              </div>
            ) : null}
            <Button
              size="sm"
              variant="ghost"
              className="h-8"
              onClick={() => {
                cancelledRef.current = true
                setOpen(false)
              }}
            >
              Cancel
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
