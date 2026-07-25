import { ExternalLink, Pencil } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  listenSubtitle,
  SandwalkServerCard
} from '@/components/agents/SandwalkServerCard'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { DEFAULT_BACKEND_URL } from '@/lib/backend-url'
import { openWebUiInBrowser } from '@/lib/desktop'

export function GeneralViewServerSection({
  backendUrl,
  backendVersion,
  connected,
  onChangeBackend,
  onDisconnectBackend
}: {
  backendUrl: string
  backendVersion: string | null
  connected: boolean
  onChangeBackend: (url: string, apiKey?: string) => void | Promise<void>
  onDisconnectBackend: () => void | Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [draftUrl, setDraftUrl] = useState(backendUrl)
  const [draftKey, setDraftKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [openingWeb, setOpeningWeb] = useState(false)

  useEffect(() => {
    if (!open) return
    setDraftUrl(backendUrl)
    setDraftKey('')
  }, [backendUrl, open])

  const apply = async () => {
    setBusy(true)
    try {
      await onChangeBackend(draftUrl, draftKey || undefined)
      setOpen(false)
    } finally {
      setBusy(false)
    }
  }

  const disconnect = async () => {
    setBusy(true)
    try {
      await onDisconnectBackend()
      setOpen(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-base font-semibold">Agent server</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          URL of the local or remote sandwalk API this dashboard talks to.
        </p>
      </div>

      <SandwalkServerCard
        version={backendVersion}
        running={connected}
        subtitle={listenSubtitle({
          running: connected,
          backendUrl
        })}
        actions={
          <div className="flex shrink-0 items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-muted-foreground"
              disabled={openingWeb}
              onClick={() => {
                setOpeningWeb(true)
                void openWebUiInBrowser(backendUrl).finally(() =>
                  setOpeningWeb(false)
                )
              }}
            >
              <ExternalLink className="size-3.5" />
              {openingWeb ? 'Opening…' : 'Open in Web UI'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-muted-foreground"
              onClick={() => setOpen(true)}
            >
              <Pencil className="size-3.5" />
              Edit
            </Button>
          </div>
        }
      />

      <Dialog
        open={open}
        onOpenChange={next => {
          if (busy) return
          setOpen(next)
        }}
      >
        <DialogContent className="bg-card text-card-foreground border-border gap-0 overflow-hidden rounded-2xl p-0 shadow-xl sm:max-w-md sm:rounded-2xl">
          <DialogHeader className="space-y-1.5 px-6 pt-6 pb-4 text-left">
            <DialogTitle>Manage agent server</DialogTitle>
            <DialogDescription>
              Switching servers clears this session. Sign in again if the new
              host requires an API key.
            </DialogDescription>
          </DialogHeader>

          <form
            onSubmit={event => {
              event.preventDefault()
              void apply()
            }}
          >
            <div className="space-y-4 px-6 pb-5">
              <div className="space-y-2">
                <div className="flex items-baseline justify-between gap-3">
                  <label
                    htmlFor="general-backend-url"
                    className="text-foreground text-sm font-medium"
                  >
                    Server URL
                  </label>
                  <button
                    type="button"
                    disabled={busy || draftUrl === DEFAULT_BACKEND_URL}
                    className="text-muted-foreground hover:text-foreground text-xs underline-offset-2 hover:underline disabled:pointer-events-none disabled:opacity-40"
                    onClick={() => {
                      setDraftUrl(DEFAULT_BACKEND_URL)
                      setDraftKey('')
                    }}
                  >
                    Use local default
                  </button>
                </div>
                <Input
                  id="general-backend-url"
                  value={draftUrl}
                  onChange={event => setDraftUrl(event.target.value)}
                  placeholder={DEFAULT_BACKEND_URL}
                  autoFocus
                  spellCheck={false}
                  autoComplete="url"
                  disabled={busy}
                />
              </div>

              <div className="space-y-2">
                <label
                  htmlFor="general-backend-key"
                  className="text-foreground text-sm font-medium"
                >
                  API key{' '}
                  <span className="text-muted-foreground font-normal">
                    (optional)
                  </span>
                </label>
                <Input
                  id="general-backend-key"
                  type="password"
                  value={draftKey}
                  onChange={event => setDraftKey(event.target.value)}
                  placeholder="Required only if the server enforces auth"
                  autoComplete="off"
                  disabled={busy}
                />
              </div>
            </div>

            <DialogFooter className="bg-muted/30 border-t px-6 py-4 sm:justify-between">
              <Button
                type="button"
                variant="ghost"
                disabled={busy}
                className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={() => void disconnect()}
              >
                Disconnect
              </Button>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  disabled={busy}
                  onClick={() => setOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" disabled={busy || !draftUrl.trim()}>
                  {busy ? 'Connecting…' : 'Connect'}
                </Button>
              </div>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </section>
  )
}
