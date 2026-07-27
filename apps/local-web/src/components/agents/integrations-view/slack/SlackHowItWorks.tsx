import { ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'

import { cn } from '@/lib/utils'

const COLLAPSE_KEY = 'sandwalk.slack.howitworks.collapsed'

const TABS = [
  {
    id: 'mention',
    label: 'Mention → session',
    body: 'Mention the bot in any channel it has been invited to. A new session opens here, and the answer goes back as a reply in that Slack thread.'
  },
  {
    id: 'dm',
    label: 'Direct messages',
    body: 'Message Sandwalk in a DM — no @mention needed. Follow-ups in that thread stay on the same session.'
  },
  {
    id: 'threads',
    label: 'Threads stay connected',
    body: 'After the first @mention in a channel (or any message in a DM), keep replying in the same Slack thread without tagging the bot again. It stays on the same session.'
  },
  {
    id: 'teammates',
    label: 'Allow teammates',
    body: 'Teammates are not trusted automatically. Their first message to the agent waits for your OK, then they join the People list. Sessions they trigger run on this machine, with your models and keys.'
  }
] as const

export function SlackHowItWorks() {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === '1'
    } catch {
      return false
    }
  })
  const [active, setActive] = useState<(typeof TABS)[number]['id']>('mention')

  const toggle = () => {
    setCollapsed(current => {
      const next = !current
      try {
        localStorage.setItem(COLLAPSE_KEY, next ? '1' : '0')
      } catch {
        // Storage can be unavailable; the toggle still works for this session.
      }
      return next
    })
  }

  const current = TABS.find(tab => tab.id === active) ?? TABS[0]

  return (
    <section className="border-border/70 rounded-xl border">
      <div className="flex items-center justify-between px-4 py-3">
        <h3 className="text-[13px] font-medium">
          Getting started with Slack &amp; Sandwalk
        </h3>
        <button
          type="button"
          onClick={toggle}
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-[12px]"
        >
          {collapsed ? 'Show' : 'Hide'}
          {collapsed ? (
            <ChevronDown className="size-3.5" />
          ) : (
            <ChevronUp className="size-3.5" />
          )}
        </button>
      </div>

      {collapsed ? null : (
        <div className="border-border/70 border-t">
          <div className="flex gap-1 px-3 pt-3">
            {TABS.map(tab => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActive(tab.id)}
                className={cn(
                  'rounded-md px-2.5 py-1 text-[12px] transition-colors',
                  active === tab.id
                    ? 'bg-muted text-foreground font-medium'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <p className="text-muted-foreground px-4 py-3 text-[13px] leading-relaxed">
            {current.body}
          </p>
        </div>
      )}
    </section>
  )
}
