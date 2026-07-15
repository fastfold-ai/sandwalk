import { Loader2 } from 'lucide-react'
import { useState } from 'react'

import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { ErrorPage } from '@/components/ErrorPage'
import { MirageBackground } from '@/components/MirageBackground'
import { ThemeToggle } from '@/components/ThemeToggle'
import { cn } from '@/lib/utils'

import { LoginHelpDialog } from './login-view-help-dialog'

export function LoginView({
  onSubmit,
  submitting = false,
  error = null,
  onRetry,
  className
}: {
  onSubmit: (apiKey: string, remember: boolean) => void | Promise<void>
  submitting?: boolean
  error?: unknown | null
  onRetry?: () => void
  className?: string
}) {
  const [apiKey, setApiKey] = useState('')
  const [remember, setRemember] = useState(true)

  return (
    <div
      className={cn(
        'bg-background text-foreground relative h-full min-h-full',
        className
      )}
    >
      <main className="relative isolate grid h-full min-h-full place-items-center overflow-hidden p-6">
        <MirageBackground />

        <div className="relative z-10 flex w-full max-w-[380px] flex-col items-center">
          <div className="mb-8 flex flex-col items-center gap-3">
            <AuraIconPulse className="text-foreground h-14 w-14 [filter:drop-shadow(0_0_10px_hsl(var(--background)/0.95))_drop-shadow(0_0_22px_hsl(var(--background)/0.9))]" />
            <h1 className="font-brand text-foreground text-[28px] font-normal tracking-tight [text-shadow:0_1px_8px_hsl(var(--background)/0.95),0_0_20px_hsl(var(--background)/0.9)]">
              sandwalk
            </h1>
          </div>

          {error ? (
            <div className="mb-4 w-full">
              <ErrorPage
                variant="inline"
                error={error}
                onRetry={onRetry}
                retryLabel="Retry connection"
              />
            </div>
          ) : null}

          <form
            className="bg-card border-border w-full rounded-2xl border px-8 py-8 shadow-[0_8px_30px_rgb(0,0,0,0.06)] dark:shadow-none"
            onSubmit={event => {
              event.preventDefault()
              void onSubmit(apiKey.trim(), remember)
            }}
          >
            <label
              htmlFor="sandwalk-api-key"
              className="text-muted-foreground mb-2 block text-[11px] font-medium tracking-[0.08em] uppercase"
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
              className="border-input bg-background text-foreground placeholder:text-muted-foreground focus:border-ring focus:ring-ring/30 h-11 w-full rounded-lg border px-3 text-sm outline-none focus:ring-2"
            />

            <label className="text-muted-foreground mt-4 flex cursor-pointer items-center gap-2.5 text-sm select-none">
              <input
                type="checkbox"
                className="border-input accent-primary size-4 shrink-0 rounded"
                checked={remember}
                onChange={event => setRemember(event.target.checked)}
              />
              <span>Stay signed in for 30 days</span>
            </label>

            <button
              type="submit"
              disabled={submitting || !apiKey.trim()}
              className="bg-primary text-primary-foreground mt-6 flex h-11 w-full items-center justify-center gap-2 rounded-lg text-sm font-semibold transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {submitting ? <Loader2 className="size-4 animate-spin" /> : null}
              Sign in
            </button>

            <div className="mt-4 flex justify-center">
              <LoginHelpDialog />
            </div>
          </form>

          <div className="mt-10 flex flex-col items-center gap-2.5">
            <p className="text-foreground/80 text-center text-sm font-medium [text-shadow:0_1px_6px_hsl(var(--background)/0.95),0_0_14px_hsl(var(--background)/0.85)]">
              A thinking path for open science
            </p>
            <p className="text-muted-foreground flex items-center gap-1.5 text-[11px]">
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
      <ThemeToggle />
    </div>
  )
}
