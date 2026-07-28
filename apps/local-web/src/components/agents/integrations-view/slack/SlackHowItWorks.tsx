import {
  AtSign,
  Cable,
  MessageSquare,
  MessagesSquare,
  Radio,
  Users
} from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { INTEGRATION_ICONS } from '@/components/agents/IntegrationIcon'

const FASTFOLD_ICON = INTEGRATION_ICONS['fastfold-cloud']
const FASTFOLD_CLOUD_PATH = '/dashboard/integrations/fastfold-cloud'

const ROWS: {
  id: string
  icon: typeof AtSign
  title: string
  body: ReactNode
}[] = [
  {
    id: 'mention',
    icon: AtSign,
    title: 'Mention @Sandwalk',
    body: 'Invite the bot to any channel, then @mention it to open a session here.'
  },
  {
    id: 'dm',
    icon: MessageSquare,
    title: 'Direct messages',
    body: 'Message Sandwalk in a DM — no @mention needed.'
  },
  {
    id: 'threads',
    icon: MessagesSquare,
    title: 'Reply in threads',
    body: 'Answers go back in the Slack thread. Follow-ups stay on the same session.'
  },
  {
    id: 'relay',
    icon: Radio,
    title: 'Relay mode',
    body: (
      <>
        For paid Slack accounts with the Agent capability — you’ll need a{' '}
        <Link
          to={FASTFOLD_CLOUD_PATH}
          className="text-foreground hover:text-foreground/80 inline-flex items-center gap-1 font-medium underline underline-offset-2"
        >
          <img
            src={FASTFOLD_ICON.src}
            alt=""
            className="size-3.5 object-contain"
          />
          FastFold account
        </Link>
        .
      </>
    )
  },
  {
    id: 'socket',
    icon: Cable,
    title: 'Socket mode',
    body: 'For free Slack workspaces — connect with app tokens over Socket Mode.'
  },
  {
    id: 'teammates',
    icon: Users,
    title: 'Allow teammates',
    body: 'New people wait for your OK once, then join People. Their sessions use this machine.'
  }
]

export function SlackHowItWorks() {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium">How it works</h3>
      <div className="bg-muted/20 border-border/60 divide-y overflow-hidden rounded-xl border">
        {ROWS.map(row => {
          const Icon = row.icon
          return (
            <div key={row.id} className="flex items-start gap-3 px-4 py-3">
              <Icon className="text-muted-foreground mt-0.5 size-5 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-medium">{row.title}</p>
                <p className="text-muted-foreground mt-0.5 text-sm">
                  {row.body}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
