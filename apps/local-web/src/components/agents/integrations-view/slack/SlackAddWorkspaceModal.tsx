import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { Check, Copy, ExternalLink, Loader2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { copyText } from '@/lib/clipboard'
import { openInSystemBrowser } from '@/lib/desktop'
import { cn } from '@/lib/utils'

type Mode = 'one-click' | 'manual'

/** Long enough to read Slack's consent screen without hanging forever. */
const ONE_CLICK_TIMEOUT_MS = 5 * 60 * 1000
const ONE_CLICK_POLL_MS = 2000

export function SlackAddWorkspaceModal({
  open,
  client,
  busy,
  updatingWorkspace,
  onOpenChange,
  onConnect,
  onImported
}: {
  open: boolean
  client: LocalAgentClient
  busy: boolean
  /** Workspace name when re-pasting tokens rather than adding a new one. */
  updatingWorkspace?: string | null
  onOpenChange: (open: boolean) => void
  onConnect: (input: { botToken: string; appToken: string }) => Promise<boolean>
  /** Called once a one-click install has been adopted, so the panel reloads. */
  onImported?: () => void
}) {
  const updating = Boolean(updatingWorkspace)
  const [mode, setMode] = useState<Mode>('manual')
  const [botToken, setBotToken] = useState('')
  const [appToken, setAppToken] = useState('')
  const [manifest, setManifest] = useState<string>('')
  const [steps, setSteps] = useState<string[]>([])
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>(
    'idle'
  )
  const [waiting, setWaiting] = useState(false)
  const [oneClickError, setOneClickError] = useState<string | null>(null)
  // Stops the poll loop writing state after the modal closes.
  const cancelledRef = useRef(false)

  useEffect(() => {
    if (!open || manifest) return
    void client
      .getSlackManifest()
      .then(result => {
        setManifest(result.manifest)
        setSteps(result.steps)
      })
      .catch(() => {
        setManifest('')
        setSteps([])
      })
  }, [client, manifest, open])

  useEffect(() => {
    cancelledRef.current = !open
    if (open) return
    setBotToken('')
    setAppToken('')
    setCopyState('idle')
    setWaiting(false)
    setOneClickError(null)
  }, [open])

  const submit = async () => {
    const ok = await onConnect({ botToken, appToken })
    if (ok) onOpenChange(false)
  }

  /**
   * Open Slack's install page, then poll until the install lands.
   *
   * The desktop never sees the OAuth callback — it happens in the browser
   * against FastFold Cloud — so the only way to know it finished is to ask.
   */
  const startOneClick = async () => {
    setOneClickError(null)
    let authUrl: string
    try {
      authUrl = (await client.startSlackOneClick()).authUrl
    } catch (error) {
      setOneClickError(
        error instanceof Error
          ? error.message
          : 'Could not start the Slack install.'
      )
      return
    }

    openInSystemBrowser(authUrl)
    setWaiting(true)
    const deadline = Date.now() + ONE_CLICK_TIMEOUT_MS
    while (Date.now() < deadline) {
      await new Promise(resolve => window.setTimeout(resolve, ONE_CLICK_POLL_MS))
      if (cancelledRef.current) return
      try {
        const result = await client.importSlackOneClick()
        if (result.data.length > 0) {
          setWaiting(false)
          onImported?.()
          onOpenChange(false)
          return
        }
      } catch {
        // Transient while the user is still in the browser; keep polling.
      }
    }
    setWaiting(false)
    setOneClickError(
      'No workspace arrived. Finish the approval in Slack and try again.'
    )
  }

  const copyManifest = async () => {
    const ok = await copyText(manifest)
    setCopyState(ok ? 'copied' : 'failed')
    window.setTimeout(() => setCopyState('idle'), ok ? 1500 : 4000)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(90dvh,48rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-lg">
        <DialogHeader className="space-y-1.5 px-5 pt-5 text-left">
          <DialogTitle className="text-base">
            {updating ? `Update tokens · ${updatingWorkspace}` : 'Add a workspace'}
          </DialogTitle>
          <DialogDescription className="text-[12px]">
            {updating
              ? 'Reinstalling the Slack app issues a new bot token. Your People and Listening settings are kept.'
              : 'Connect Slack so mentions open a session here.'}
          </DialogDescription>
        </DialogHeader>

        {updating ? null : (
          <div className="px-5 pt-4">
            <div className="bg-muted/60 inline-flex rounded-full p-0.5">
              {(
                [
                  ['one-click', 'One click'],
                  ['manual', 'Manual']
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMode(value)}
                  className={cn(
                    'rounded-full px-3 py-1 text-[12px] transition-colors',
                    mode === value
                      ? 'bg-background text-foreground font-medium shadow-sm'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-auto px-5 py-4">
          {mode === 'one-click' && !updating ? (
            <div className="space-y-3">
              <p className="text-muted-foreground text-[13px] leading-relaxed">
                Approve Sandwalk for your workspace in the browser — no tokens to
                copy, and it works for any number of workspaces.
              </p>

              {oneClickError ? (
                <div className="border-destructive/40 bg-destructive/5 rounded-lg border p-3">
                  <p className="text-[12px] leading-relaxed">{oneClickError}</p>
                  <Button
                    size="sm"
                    variant="outline"
                    className="mt-3 h-8"
                    onClick={() => setMode('manual')}
                  >
                    Use Manual setup instead
                  </Button>
                </div>
              ) : null}

              {waiting ? (
                <div className="border-border/70 bg-muted/30 flex items-center gap-2 rounded-lg border p-3">
                  <Loader2 className="size-3.5 shrink-0 animate-spin" />
                  <p className="text-[12px] leading-relaxed">
                    Waiting for you to approve Sandwalk in Slack…
                  </p>
                </div>
              ) : null}

              <Button
                size="sm"
                className="h-8"
                disabled={busy || waiting}
                onClick={() => void startOneClick()}
              >
                {waiting ? 'Waiting…' : 'Add to Slack'}
                <ExternalLink className="ml-1.5 size-3.5" />
              </Button>

              <p className="text-muted-foreground text-[12px] leading-relaxed">
                One click routes Slack messages through FastFold Cloud, so it
                needs an API key. Manual runs entirely on this machine and needs
                no account — the better choice for sensitive workspaces.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {updating ? (
                <p className="text-muted-foreground text-[12px] leading-relaxed">
                  After saving a new manifest, Slack reinstalls the app and
                  issues a fresh bot token. Copy it from OAuth &amp; Permissions.
                  The app token only changes if you regenerate it.
                </p>
              ) : (
                <ol className="text-muted-foreground list-inside list-decimal space-y-1 text-[12px] leading-relaxed">
                  {steps.map(step => (
                    <li key={step}>{step}</li>
                  ))}
                </ol>
              )}

              {manifest && !updating ? (
                <div className="border-border/70 rounded-lg border">
                  <div className="flex items-center justify-between px-3 py-2">
                    <span className="text-[12px] font-medium">App manifest</span>
                    <div className="flex items-center gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        className={cn(
                          'h-7 gap-1.5 text-[12px]',
                          copyState === 'failed' && 'text-destructive'
                        )}
                        onClick={() => void copyManifest()}
                      >
                        {copyState === 'copied' ? (
                          <Check className="size-3.5" />
                        ) : (
                          <Copy className="size-3.5" />
                        )}
                        {copyState === 'copied'
                          ? 'Copied'
                          : copyState === 'failed'
                            ? 'Select it manually'
                            : 'Copy'}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 gap-1.5 text-[12px]"
                        onClick={() =>
                          void openInSystemBrowser('https://api.slack.com/apps')
                        }
                      >
                        <ExternalLink className="size-3.5" />
                        Slack apps
                      </Button>
                    </div>
                  </div>
                  {/* select-all makes one click grab the whole manifest when
                      the clipboard API is unavailable. */}
                  <pre className="bg-muted/40 max-h-40 select-all overflow-auto rounded-b-lg px-3 py-2 font-mono text-[10px] leading-relaxed">
                    <code>{manifest}</code>
                  </pre>
                </div>
              ) : null}

              <div className="space-y-2">
                <Input
                  value={botToken}
                  placeholder="Bot token · xoxb-…"
                  onChange={event => setBotToken(event.target.value)}
                />
                <Input
                  value={appToken}
                  placeholder="App token · xapp-…"
                  onChange={event => setAppToken(event.target.value)}
                />
              </div>

              <p className="text-muted-foreground text-[11px] leading-relaxed">
                Both tokens are required. Socket Mode silently fails to connect
                without the app token, and Slack reports no error.
              </p>
            </div>
          )}
        </div>

        {mode === 'manual' || updating ? (
          <div className="border-border/70 flex justify-end gap-2 border-t px-5 py-3">
            <Button
              variant="ghost"
              size="sm"
              className="h-8"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              className="h-8 gap-1.5"
              disabled={busy || !botToken.trim() || !appToken.trim()}
              onClick={() => void submit()}
            >
              {busy ? <Loader2 className="size-3.5 animate-spin" /> : null}
              {updating ? 'Save tokens' : 'Connect'}
            </Button>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
