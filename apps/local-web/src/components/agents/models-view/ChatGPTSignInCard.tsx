import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { ChatGPTAuthStatus } from '@sandwalk/agent-ui-core'
import { Check, Loader, LogOut } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useChatGPTAuth } from '@/hooks/useChatGPTAuth'
import { cn } from '@/lib/utils'

/**
 * "Continue with ChatGPT" per OpenAI's Sign in with ChatGPT guidelines.
 * Uses the user's Plus/Pro plan for OpenAI models — no API key.
 */
export function ChatGPTSignInCard({
  client,
  compact = false,
  className,
  onConnected,
  onDisconnected
}: {
  client: LocalAgentClient
  /** Tighter layout for the onboarding step. */
  compact?: boolean
  className?: string
  onConnected?: (status: ChatGPTAuthStatus) => void | Promise<void>
  onDisconnected?: () => void | Promise<void>
}) {
  const auth = useChatGPTAuth(client, { onConnected })
  const busy = auth.phase === 'waiting' || auth.phase === 'disconnecting'

  return (
    <div
      className={cn(
        'border-border/70 rounded-xl border',
        compact ? 'space-y-2 p-3' : 'space-y-3 p-4',
        className
      )}
      data-testid="chatgpt-signin-card"
    >
      <div className="flex items-start gap-3">
        <span className="bg-muted/50 grid size-9 shrink-0 place-items-center rounded-lg">
          <img src="/openai.svg" alt="" className="size-5 dark:invert" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">ChatGPT plan</p>
          <p className="text-muted-foreground mt-0.5 text-xs leading-relaxed">
            {auth.status.connected
              ? 'OpenAI models run on your ChatGPT plan. Usage counts toward that plan, not an API key.'
              : 'Use your ChatGPT Plus or Pro plan for GPT models. No API key, no extra charge from Sandwalk.'}
          </p>
        </div>
        {auth.status.connected ? (
          <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            <Check className="size-3.5" />
            Connected
          </span>
        ) : null}
      </div>

      {auth.status.connected && auth.status.email ? (
        <p className="text-muted-foreground truncate font-mono text-[11px]">
          {auth.status.email}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        {auth.phase === 'loading' ? (
          // Do not flash "Continue with ChatGPT" before we know the real state.
          <Button type="button" size="sm" disabled variant="outline">
            <Loader className="size-4 animate-spin" />
            Checking…
          </Button>
        ) : auth.status.connected ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => {
              void auth.disconnect().then(() => onDisconnected?.())
            }}
          >
            {auth.phase === 'disconnecting' ? (
              <Loader className="size-4 animate-spin" />
            ) : (
              <LogOut className="size-4" />
            )}
            Disconnect
          </Button>
        ) : auth.phase === 'waiting' ? (
          <>
            <Button type="button" size="sm" disabled>
              <Loader className="size-4 animate-spin" />
              Waiting for browser…
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => auth.cancel()}
            >
              Cancel
            </Button>
          </>
        ) : (
          <Button
            type="button"
            size="sm"
            onClick={() => void auth.signIn()}
            className="gap-2"
          >
            <img src="/openai.svg" alt="" className="size-4 invert dark:invert-0" />
            Continue with ChatGPT
          </Button>
        )}
      </div>

      {auth.error ? (
        <p className="text-destructive text-xs">{auth.error}</p>
      ) : auth.status.connected ? null : (
        <p className="text-muted-foreground text-[11px] leading-relaxed">
          Plus plans share one 5-hour usage window across every app connected to
          ChatGPT. Pro plans have no 5-hour cap.
        </p>
      )}
    </div>
  )
}
