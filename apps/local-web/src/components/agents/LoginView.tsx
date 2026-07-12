import { useState } from 'react'
import { Check, CircleHelp, Copy, Loader2, Terminal } from 'lucide-react'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { MirageBackground } from '@/components/MirageBackground'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

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
    description: 'Turns auth on. Restart serve if it is already running.'
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

function CommandRow({
  command,
  copied,
  onCopy
}: {
  command: string
  copied: boolean
  onCopy: () => void
}) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-neutral-200 bg-neutral-50 p-2.5">
      <Terminal className="size-4 shrink-0 text-neutral-400" />
      <code className="min-w-0 flex-1 truncate font-mono text-[13px] text-neutral-900">
        {command}
      </code>
      <button
        type="button"
        className="inline-flex size-7 shrink-0 items-center justify-center rounded-md text-neutral-500 transition-colors hover:bg-neutral-200/70 hover:text-neutral-900"
        onClick={onCopy}
        aria-label={`Copy ${command}`}
        title="Copy command"
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </button>
    </div>
  )
}

export function LoginView({
  onSubmit,
  submitting = false,
  className
}: {
  onSubmit: (apiKey: string, remember: boolean) => void | Promise<void>
  submitting?: boolean
  className?: string
}) {
  const [apiKey, setApiKey] = useState('')
  const [remember, setRemember] = useState(true)
  const [helpOpen, setHelpOpen] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const copyCommand = (id: string, command: string) => {
    void navigator.clipboard.writeText(command)
    setCopiedId(id)
    window.setTimeout(() => {
      setCopiedId(current => (current === id ? null : current))
    }, 2000)
  }

  return (
    <main
      className={cn(
        'relative isolate grid min-h-full place-items-center overflow-hidden bg-[#f5f5f5] p-6 text-neutral-950 dark:bg-neutral-950 dark:text-neutral-50',
        className
      )}
    >
      <MirageBackground />

      <div className="relative z-10 flex w-full max-w-[380px] flex-col items-center">
        <div className="mb-8 flex flex-col items-center gap-3">
          <AuraIconPulse className="h-14 w-14 text-black [filter:drop-shadow(0_0_10px_rgba(245,245,245,0.95))_drop-shadow(0_0_22px_rgba(245,245,245,0.9))] dark:text-white dark:[filter:drop-shadow(0_0_10px_rgba(10,10,10,0.95))_drop-shadow(0_0_22px_rgba(10,10,10,0.9))]" />
          <h1 className="text-[28px] font-bold tracking-tight text-black [text-shadow:0_1px_8px_rgba(245,245,245,0.95),0_0_20px_rgba(245,245,245,0.9)] dark:text-white dark:[text-shadow:0_1px_8px_rgba(10,10,10,0.95),0_0_20px_rgba(10,10,10,0.9)]">
            Sandwalk
          </h1>
        </div>

        <form
          className="w-full rounded-2xl bg-white px-8 py-8 shadow-[0_8px_30px_rgb(0,0,0,0.06)] dark:border dark:border-neutral-800 dark:bg-neutral-900 dark:shadow-none"
          onSubmit={event => {
            event.preventDefault()
            void onSubmit(apiKey.trim(), remember)
          }}
        >
          <label
            htmlFor="sandwalk-api-key"
            className="mb-2 block text-[11px] font-medium tracking-[0.08em] text-neutral-400 uppercase"
          >
            API Key
          </label>
          <input
            id="sandwalk-api-key"
            type="password"
            autoFocus
            autoComplete="off"
            spellCheck={false}
            value={apiKey}
            onChange={event => setApiKey(event.target.value)}
            placeholder="Enter your API key"
            className="h-11 w-full rounded-lg border border-neutral-200 bg-white px-3 text-sm text-neutral-900 outline-none placeholder:text-neutral-400 focus:border-neutral-400 dark:border-neutral-700 dark:bg-neutral-950 dark:text-neutral-50 dark:focus:border-neutral-500"
          />

          <label className="mt-4 flex cursor-pointer items-center gap-2.5 text-sm text-neutral-500 select-none dark:text-neutral-400">
            <input
              type="checkbox"
              className="size-4 shrink-0 rounded border-neutral-300 accent-black dark:accent-white"
              checked={remember}
              onChange={event => setRemember(event.target.checked)}
            />
            <span>Stay signed in for 30 days</span>
          </label>

          <button
            type="submit"
            disabled={submitting || !apiKey.trim()}
            className="mt-6 flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-black text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black"
          >
            {submitting ? (
              <Loader2 className="size-4 animate-spin" />
            ) : null}
            Sign in
          </button>

          <div className="mt-4 flex justify-center">
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
                  className="inline-flex items-center gap-1.5 text-sm text-neutral-400 transition-colors hover:text-neutral-700 dark:hover:text-neutral-200"
                  aria-label="Help with API keys"
                >
                  <CircleHelp className="size-4" />
                  Help
                </button>
              </DialogTrigger>
              <DialogContent className="flex max-h-[min(90vh,44rem)] max-w-2xl flex-col gap-0 overflow-hidden rounded-2xl border-neutral-200 bg-white p-0 text-neutral-950 shadow-xl sm:rounded-2xl">
                <DialogHeader className="shrink-0 space-y-2 px-6 pt-6 pb-2 text-left">
                  <DialogTitle className="text-lg font-semibold">
                    How to get an API key
                  </DialogTitle>
                  <DialogDescription className="text-sm text-neutral-500">
                    Use the Sandwalk CLI on any OS, or the Mac menubar app on
                    macOS. Restart{' '}
                    <code className="font-mono text-[12px] text-neutral-700">
                      sandwalk serve
                    </code>{' '}
                    after changing auth settings.
                  </DialogDescription>
                </DialogHeader>

                <ScrollArea className="h-[min(55vh,28rem)] px-6">
                  <div className="space-y-4 py-2 pr-3">
                    <div className="rounded-xl border border-neutral-200 bg-neutral-50 px-3.5 py-3">
                      <p className="text-sm font-semibold text-neutral-900">
                        Mac app
                      </p>
                      <p className="mt-1 text-sm leading-relaxed text-neutral-500">
                        Open the Sandwalk menubar app →{' '}
                        <span className="font-medium text-neutral-700">
                          Settings…
                        </span>{' '}
                        →{' '}
                        <span className="font-medium text-neutral-700">
                          Security
                        </span>
                        . There you can show, copy, or regenerate your API key
                        and toggle whether login is required.
                      </p>
                    </div>

                    <div>
                      <p className="mb-3 text-sm font-semibold text-neutral-900">
                        CLI commands
                      </p>
                      <div className="space-y-3.5">
                        {HELP_COMMANDS.map(item => (
                          <div key={item.id}>
                            <p className="mb-1.5 text-xs font-medium text-neutral-600">
                              {item.title}
                            </p>
                            <CommandRow
                              command={item.command}
                              copied={copiedId === item.id}
                              onCopy={() =>
                                copyCommand(item.id, item.command)
                              }
                            />
                            <p className="mt-1.5 text-xs text-neutral-500">
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
                    className="h-10 rounded-lg bg-black px-4 text-sm font-semibold text-white transition-opacity hover:opacity-90"
                    onClick={() => setHelpOpen(false)}
                  >
                    Got it
                  </button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </form>

        <div className="mt-10 flex flex-col items-center gap-2.5">
          <p className="text-center text-sm font-medium text-neutral-700 [text-shadow:0_1px_6px_rgba(245,245,245,0.95),0_0_14px_rgba(245,245,245,0.85)] dark:text-neutral-200 dark:[text-shadow:0_1px_6px_rgba(10,10,10,0.95),0_0_14px_rgba(10,10,10,0.85)]">
            A thinking path for open science
          </p>
          <p className="flex items-center gap-1.5 text-[11px] text-neutral-500 dark:text-neutral-400">
            <span>by</span>
            <img
              src="/logo_fastfold_black.svg"
              alt="Fastfold"
              className="h-3 w-auto dark:hidden"
            />
            <img
              src="/logo_fastfold_white.svg"
              alt="Fastfold"
              className="hidden h-3 w-auto dark:block"
            />
          </p>
        </div>
      </div>
    </main>
  )
}
