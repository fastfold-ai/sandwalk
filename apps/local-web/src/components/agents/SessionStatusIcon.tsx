import type { AgentSession } from '@sandwalk/agent-ui-core'
import { CircleCheck, Loader, ShieldAlert } from 'lucide-react'

export function SessionStatusIcon({ status }: { status: AgentSession['status'] }) {
  if (status === 'awaiting_approval') {
    return (
      <ShieldAlert
        className="size-3.5 shrink-0 text-amber-500"
        aria-label="Awaiting approval"
      />
    )
  }
  if (status === 'running') {
    return (
      <Loader
        className="text-muted-foreground/80 size-3.5 shrink-0 animate-spin"
        aria-hidden
      />
    )
  }
  if (status === 'error') {
    return (
      <span className="border-destructive size-3.5 shrink-0 rounded-full border" />
    )
  }
  if (status === 'interrupted') {
    return (
      <span className="size-3.5 shrink-0 rounded-full border border-amber-500" />
    )
  }
  return <CircleCheck className="text-muted-foreground/70 size-3.5 shrink-0" />
}
