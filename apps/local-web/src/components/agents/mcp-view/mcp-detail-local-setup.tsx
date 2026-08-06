import { Check, Copy, Download, Loader2, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'

import type { McpDetailViewState } from './use-mcp-detail-view'

const PLUGIN_ZIP = 'https://sandwalk.sh/pymol/plugin.zip'

export function McpDetailLocalSetupDialog({
  open,
  onOpenChange,
  state,
  onInstallLocal
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  state: McpDetailViewState
  onInstallLocal?: (opts?: { force?: boolean }) => Promise<void>
}) {
  const entry = state.catalogEntry
  if (!entry || entry.transport !== 'stdio') return null

  const setupUrl = entry.setupUrl || PLUGIN_ZIP
  const [copied, setCopied] = useState(false)
  const [installing, setInstalling] = useState(false)

  const copyUrl = async () => {
    try {
      await navigator.clipboard.writeText(setupUrl)
      setCopied(true)
      toast.success('Plugin zip URL copied')
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      toast.error('Could not copy URL')
    }
  }

  const runInstall = async (force = false) => {
    if (!onInstallLocal) return
    setInstalling(true)
    try {
      await onInstallLocal({ force })
      toast.success(force ? 'Launcher reinstalled' : 'Launcher installed', {
        description: entry.name
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err), {
        description: entry.name
      })
    } finally {
      setInstalling(false)
    }
  }

  const steps = [
    {
      title: 'Install the PyMOL plugin',
      body: (
        <>
          In PyMOL → Plugin Manager → Install New Plugin → Install from URL →
          Fetch. Works for commercial and open-source PyMOL.
        </>
      )
    },
    {
      title: 'One-time launcher setup',
      body: (
        <div className="space-y-2">
          <p>
            Run{' '}
            <code className="bg-muted rounded px-1 py-0.5 text-[11px]">
              sandwalk mcp install pymol
            </code>
            {entry.configured ? (
              <>
                {' '}
                or reinstall with{' '}
                <code className="bg-muted rounded px-1 py-0.5 text-[11px]">
                  sandwalk mcp install pymol --force
                </code>
              </>
            ) : null}
            .
          </p>
          {onInstallLocal ? (
            <div className="flex flex-wrap gap-2">
              {!entry.configured ? (
                <Button
                  type="button"
                  size="sm"
                  className="h-7 gap-1.5 text-xs"
                  disabled={installing}
                  onClick={() => void runInstall(false)}
                >
                  {installing ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Download className="size-3.5" />
                  )}
                  Install launcher
                </Button>
              ) : (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 gap-1.5 text-xs"
                  disabled={installing}
                  onClick={() => void runInstall(true)}
                >
                  {installing ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <RotateCcw className="size-3.5" />
                  )}
                  Reinstall launcher
                </Button>
              )}
            </div>
          ) : null}
        </div>
      )
    },
    {
      title: 'Start Listening',
      body: (
        <>
          Open <strong>Sandwalk PyMOL MCP</strong> from the Plugin menu and
          click <strong>Start Listening</strong> (required each session). Auth
          token is created automatically.
        </>
      )
    },
    {
      title: 'Enable in Sandwalk',
      body: (
        <>
          Use the enable toggle on this page. Agents can call PyMOL tools while
          the plugin is listening.
        </>
      )
    }
  ]

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg gap-4">
        <DialogHeader>
          <DialogTitle>Setup checklist</DialogTitle>
          <DialogDescription>
            Local stdio bridge to a live PyMOL session via agentic-pymol.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2">
          <code className="bg-muted max-w-full truncate rounded px-2 py-1 text-xs">
            {setupUrl}
          </code>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 gap-1.5 text-xs"
            onClick={() => void copyUrl()}
          >
            {copied ? (
              <Check className="size-3.5" />
            ) : (
              <Copy className="size-3.5" />
            )}
            Copy URL
          </Button>
        </div>

        <ol className="space-y-3">
          {steps.map((step, index) => (
            <li key={step.title} className="flex gap-3 text-sm">
              <span className="bg-muted text-muted-foreground flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-medium">
                {index + 1}
              </span>
              <div className="min-w-0 space-y-0.5">
                <div className="font-medium">{step.title}</div>
                <div className="text-muted-foreground leading-relaxed">
                  {step.body}
                </div>
              </div>
            </li>
          ))}
        </ol>

        {entry.command ? (
          <p className="text-muted-foreground text-xs">
            Launcher command:{' '}
            <code className="bg-muted rounded px-1 py-0.5">
              {entry.command}
            </code>
            {entry.configured ? ' (ready)' : ' (not installed yet)'}
          </p>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
