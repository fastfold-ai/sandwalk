import { Loader } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { openInSystemBrowser } from '@/lib/desktop'

import { VERCEL_SETUP_COMMANDS } from '../integrations-view-shared'

const VERCEL_DASHBOARD_URL = 'https://vercel.com/dashboard'
const TOKEN_ENV = 'VERCEL_OIDC_TOKEN'

export function VercelOidcModal({
  open,
  busy,
  configured,
  setupUrl,
  onOpenChange,
  onSaveToken,
  onRunTerminal
}: {
  open: boolean
  busy: boolean
  configured: boolean
  setupUrl?: string | null
  onOpenChange: (open: boolean) => void
  onSaveToken: (token: string) => Promise<void>
  onRunTerminal: () => void
}) {
  const [token, setToken] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) return
    setToken('')
    setSaving(false)
  }, [open])

  const submit = async () => {
    const value = token.trim()
    if (!value) return
    setSaving(true)
    try {
      await onSaveToken(value)
      onOpenChange(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(90dvh,48rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-lg">
        <DialogHeader className="space-y-1.5 px-5 pt-5 text-left">
          <DialogTitle className="text-base">
            {configured ? 'Update Vercel OIDC' : 'Add Vercel OIDC'}
          </DialogTitle>
          <DialogDescription className="text-[12px]">
            Paste a Vercel OIDC token manually if you already have one.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-auto px-5 py-4">
          <ol className="text-muted-foreground list-decimal space-y-1.5 pl-4 text-[12px] leading-relaxed">
            <li>
              In{' '}
              <button
                type="button"
                className="text-foreground underline underline-offset-2"
                onClick={() =>
                  void openInSystemBrowser(setupUrl || VERCEL_DASHBOARD_URL)
                }
              >
                Vercel Dashboard ↗
              </button>
              , open the target project, then go to{' '}
              <code className="text-foreground">
                Settings → Security → OIDC Federation
              </code>{' '}
              and enable it.
            </li>
            <li>
              Prefer one-click?{' '}
              <button
                type="button"
                className="text-foreground font-medium underline underline-offset-2"
                onClick={() => {
                  onOpenChange(false)
                  onRunTerminal()
                }}
              >
                Run setup terminal
              </button>{' '}
              — or run the commands below yourself and paste{' '}
              <code className="text-foreground">{TOKEN_ENV}</code>.
            </li>
            <li>Click Save &amp; Test.</li>
          </ol>

          <pre className="bg-muted/40 max-h-40 overflow-auto rounded-lg border p-3 font-mono text-[11px] leading-relaxed">
            <code>{VERCEL_SETUP_COMMANDS.join('\n')}</code>
          </pre>

          <div className="space-y-2">
            <label
              className="text-[12px] font-medium"
              htmlFor="vercel-oidc-token"
            >
              {TOKEN_ENV}
            </label>
            <Input
              id="vercel-oidc-token"
              value={token}
              placeholder={`Paste ${TOKEN_ENV}`}
              onChange={event => setToken(event.target.value)}
              autoComplete="off"
              spellCheck={false}
            />
          </div>
        </div>

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
            disabled={busy || saving || !token.trim()}
            onClick={() => void submit()}
          >
            {saving || busy ? (
              <Loader className="size-3.5 animate-spin" />
            ) : null}
            Save &amp; Test
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
