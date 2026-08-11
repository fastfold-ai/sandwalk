import { ArrowUpRight, CircleHelp } from 'lucide-react'
import { useState } from 'react'

import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'

import { CommandRow, copyCommand, MacAppIcon } from './command-help-shared'

const SANDWALK_SECURITY_DEEP_LINK = 'sandwalk://settings/security'

const HELP_COMMANDS = [
  {
    id: 'generate',
    title: 'Generate an API key',
    command: 'sandwalk auth generate',
    description: 'Creates a new key and prints it once.'
  },
  {
    id: 'enable',
    title: 'Require login',
    command: 'sandwalk auth enable',
    description: 'Turns auth on so the local UI and API require a key.'
  },
  {
    id: 'show',
    title: 'Show your key',
    command: 'sandwalk auth show',
    description: 'Prints the current API key so you can paste it here.'
  },
  {
    id: 'disable',
    title: 'Disable login',
    command: 'sandwalk auth disable',
    description: 'Turns auth off so the local UI no longer requires a key.'
  }
] as const

export function LoginHelpDialog() {
  const [helpOpen, setHelpOpen] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  return (
    <Dialog
      open={helpOpen}
      onOpenChange={open => {
        setHelpOpen(open)
        if (!open) setCopiedId(null)
      }}
    >
      <DialogTrigger asChild>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 text-sm transition-colors"
          aria-label="Help with API keys"
        >
          <CircleHelp className="size-4" />
          Help
        </button>
      </DialogTrigger>
      <DialogContent className="bg-card text-card-foreground border-border flex max-h-[min(90vh,44rem)] max-w-2xl flex-col gap-0 overflow-hidden rounded-2xl p-0 shadow-xl sm:rounded-2xl">
        <DialogHeader className="shrink-0 space-y-2 px-6 pt-6 pb-2 text-left">
          <DialogTitle className="text-lg font-semibold">
            How to get an API key
          </DialogTitle>
        </DialogHeader>

        <ScrollArea className="h-[min(55vh,28rem)] px-6">
          <div className="space-y-4 py-2 pr-3">
            <div className="bg-muted/50 border-border rounded-xl border px-3.5 py-3">
              <div className="flex items-start gap-3">
                <MacAppIcon />
                <div className="min-w-0 flex-1">
                  <p className="text-foreground text-sm font-semibold">Mac app</p>
                  <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
                    Open sandwalk, then go to{' '}
                    <span className="text-foreground font-medium">General</span>{' '}
                    →{' '}
                    <span className="text-foreground font-medium">Security</span>.
                    Show, copy, or regenerate your key and turn login on or off —
                    the app applies changes automatically.
                  </p>
                  <a
                    href={SANDWALK_SECURITY_DEEP_LINK}
                    className="bg-background text-foreground border-border hover:bg-muted mt-3 inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-xs font-medium transition-colors"
                  >
                    Open Security settings
                    <ArrowUpRight className="size-3.5" />
                  </a>
                </div>
              </div>
            </div>

            <div>
              <p className="text-foreground mb-3 text-sm font-semibold">
                CLI commands
              </p>
              <div className="space-y-3.5">
                {HELP_COMMANDS.map(item => (
                  <div key={item.id}>
                    <p className="text-muted-foreground mb-1.5 text-xs font-medium">
                      {item.title}
                    </p>
                    <CommandRow
                      command={item.command}
                      copied={copiedId === item.id}
                      onCopy={() => copyCommand(item.id, item.command, setCopiedId)}
                    />
                    <p className="text-muted-foreground mt-1.5 text-xs">
                      {item.description}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </ScrollArea>

        <DialogFooter className="shrink-0 px-6 pt-2 pb-5 sm:justify-end">
          <button
            type="button"
            className="bg-primary text-primary-foreground h-10 rounded-lg px-4 text-sm font-semibold transition-opacity hover:opacity-90"
            onClick={() => setHelpOpen(false)}
          >
            Got it
          </button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
