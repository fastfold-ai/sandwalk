import { Check, Copy, Download, ExternalLink, Loader2, RotateCcw } from 'lucide-react'
import { useState, type ReactNode } from 'react'
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

import type { McpDetailViewState } from './use-mcp-detail-view'

const PLUGIN_ZIP = 'https://sandwalk.sh/pymol/plugin.zip'
const PYMOL_URL = 'https://www.pymol.org/'
const RAYMOL_URL = 'https://raymol.io/'

type SetupStep = { title: string; body: ReactNode }

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

  const isRaymol = entry.id === 'raymol'
  const setupUrl = entry.setupUrl || (isRaymol ? RAYMOL_URL : PLUGIN_ZIP)
  const [copied, setCopied] = useState(false)
  const [installing, setInstalling] = useState(false)

  const openUrl = () => {
    void openInSystemBrowser(setupUrl)
  }

  const copyUrl = async () => {
    try {
      await navigator.clipboard.writeText(setupUrl)
      setCopied(true)
      toast.success(isRaymol ? 'Download URL copied' : 'Plugin zip URL copied')
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
      toast.success(
        force
          ? isRaymol
            ? 'RayMol bridge re-checked'
            : 'Launcher reinstalled'
          : isRaymol
            ? 'RayMol bridge ready'
            : 'Launcher installed',
        { description: entry.name }
      )
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err), {
        description: entry.name
      })
    } finally {
      setInstalling(false)
    }
  }

  const installButtons = onInstallLocal ? (
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
          {isRaymol ? 'Install bridge' : 'Install launcher'}
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
          {isRaymol ? 'Re-check bridge' : 'Reinstall launcher'}
        </Button>
      )}
    </div>
  ) : null

  const pymolSteps: SetupStep[] = [
    {
      title: 'Install PyMOL',
      body: (
        <p>
          If you do not already have PyMOL, download it from{' '}
          <button
            type="button"
            className="text-foreground inline-flex items-center gap-1 underline underline-offset-2"
            onClick={() => void openInSystemBrowser(PYMOL_URL)}
          >
            pymol.org
            <ExternalLink className="size-3" />
          </button>
          . Commercial and open-source builds both work.
        </p>
      )
    },
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
          {installButtons}
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

  const raymolSteps: SetupStep[] = [
    {
      title: 'Install RayMol',
      body: (
        <div className="space-y-2">
          <p>
            Get RayMol from{' '}
            <button
              type="button"
              className="text-foreground inline-flex items-center gap-1 underline underline-offset-2"
              onClick={() => void openInSystemBrowser(RAYMOL_URL)}
            >
              raymol.io
              <ExternalLink className="size-3" />
            </button>{' '}
            — use the <strong>direct DMG</strong> or{' '}
            <code className="bg-muted rounded px-1 py-0.5 text-[11px]">
              brew install --cask javierbq/raymol/raymol
            </code>
            . Mac App Store builds do not include MCP.
          </p>
        </div>
      )
    },
    {
      title: 'Enable MCP in RayMol',
      body: (
        <>
          Open RayMol → toolbar <strong>RayMol MCP</strong> → toggle{' '}
          <strong>Enable MCP server</strong>. The server listens on localhost
          only (token-protected).
        </>
      )
    },
    {
      title: 'Allow MCP access in RayMol',
      body: (
        <>
          Once MCP is on, RayMol prompts to <strong>Allow</strong> access when
          a client connects. Click <strong>Allow</strong> — otherwise the MCP
          connection will not establish and tools will fail.
        </>
      )
    },
    {
      title: 'Connect Sandwalk',
      body: (
        <div className="space-y-2">
          <p>
            Run{' '}
            <code className="bg-muted rounded px-1 py-0.5 text-[11px]">
              sandwalk mcp install raymol
            </code>{' '}
            or use the button below. Sandwalk spawns{' '}
            <code className="bg-muted rounded px-1 py-0.5 text-[11px]">
              RayMol --mcp-bridge
            </code>
            . Approve the Allow prompt in RayMol when it appears.
          </p>
          {installButtons}
        </div>
      )
    },
    {
      title: 'Enable in Sandwalk',
      body: (
        <>
          Use the enable toggle on this page. Keep RayMol open with MCP enabled
          (and access Allowed) while the agent runs.
        </>
      )
    }
  ]

  const steps = isRaymol ? raymolSteps : pymolSteps

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg gap-4">
        <DialogHeader>
          <DialogTitle>Setup checklist</DialogTitle>
          <DialogDescription>
            {isRaymol
              ? 'Local stdio bridge to RayMol via RayMol --mcp-bridge.'
              : 'Local stdio bridge to a live PyMOL session via agentic-pymol.'}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="bg-muted text-foreground hover:bg-muted/80 inline-flex max-w-full items-center gap-1.5 truncate rounded px-2 py-1 text-left text-xs underline-offset-2 hover:underline"
            onClick={openUrl}
            title="Open in browser"
          >
            <code className="truncate">{setupUrl}</code>
            <ExternalLink className="size-3 shrink-0 opacity-70" />
          </button>
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
            Bridge command:{' '}
            <code className="bg-muted rounded px-1 py-0.5">
              {entry.command}
              {entry.args?.length
                ? ` ${entry.args.join(' ')}`
                : isRaymol
                  ? ' --mcp-bridge'
                  : ''}
            </code>
            {entry.configured ? ' (ready)' : ' (not installed yet)'}
          </p>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
