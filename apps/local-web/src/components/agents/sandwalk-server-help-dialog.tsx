import { CircleHelp } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
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

const MANAGE_COMMANDS = [
  {
    id: 'serve',
    title: 'Start the server',
    command: 'sandwalk serve',
    description: 'Runs the sandwalk API (default http://127.0.0.1:8787).'
  },
  {
    id: 'status',
    title: 'Check auth / settings',
    command: 'sandwalk auth status',
    description: 'Shows whether API-key auth is enabled on the server.'
  }
] as const

export function SandwalkServerHelpDialog() {
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
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="text-muted-foreground shrink-0"
        >
          <CircleHelp className="size-3.5" />
          Help
        </Button>
      </DialogTrigger>
      <DialogContent className="bg-card text-card-foreground border-border flex max-h-[min(90vh,44rem)] max-w-2xl flex-col gap-0 overflow-hidden rounded-2xl p-0 shadow-xl sm:rounded-2xl">
        <DialogHeader className="shrink-0 space-y-2 px-6 pt-6 pb-2 text-left">
          <DialogTitle className="text-lg font-semibold">
            How to manage sandwalk
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
                    Use the sandwalk menubar icon →{' '}
                    <span className="text-foreground font-medium">Start</span>,{' '}
                    <span className="text-foreground font-medium">Stop</span>, or{' '}
                    <span className="text-foreground font-medium">Restart</span>.
                    That supervises the API and this web UI together when you run
                    sandwalk from the app.
                  </p>
                </div>
              </div>
            </div>

            <div>
              <p className="text-foreground mb-3 text-sm font-semibold">
                CLI commands
              </p>
              <div className="space-y-3.5">
                {MANAGE_COMMANDS.map(item => (
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
              <p className="text-muted-foreground mt-3 text-xs leading-relaxed">
                To stop a CLI-started server, interrupt the terminal with Ctrl+C,
                or quit / stop from the menubar if it is supervising the process.
                The dashboard connects to whatever host you configure — local or
                remote.
              </p>
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
