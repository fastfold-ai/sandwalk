import type {
  AgentSession,
  SlackAllowedUser,
  SlackDirectory,
  SlackSubscription,
  SlackWorkspace
} from '@sandwalk/agent-ui-core'
import { RefreshCw, X } from 'lucide-react'
import { type ReactNode, useState } from 'react'

import { Button } from '@/components/ui/button'

import {
  Avatar,
  type PickerOption,
  SlackPickerPopover
} from './SlackPickerPopover'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="border-border/70 grid grid-cols-[6rem_minmax(0,1fr)] items-start gap-3 border-t px-4 py-3">
      <span className="text-muted-foreground pt-1 text-[12px]">{label}</span>
      <div className="min-w-0">{children}</div>
    </div>
  )
}

function Chip({
  name,
  id,
  avatarUrl,
  disabled,
  onRemove
}: {
  name: string
  id: string
  avatarUrl?: string | null
  disabled?: boolean
  onRemove: () => void
}) {
  return (
    <span
      title={`id ${id}`}
      className="bg-muted/70 inline-flex items-center gap-1.5 rounded-full py-0.5 pl-1 pr-1.5 text-[12px]"
    >
      <Avatar name={name} src={avatarUrl} />
      <span className="max-w-40 truncate">{name}</span>
      <button
        type="button"
        disabled={disabled}
        onClick={onRemove}
        aria-label={`Remove ${name}`}
        className="text-muted-foreground hover:text-foreground disabled:opacity-40"
      >
        <X className="size-3" />
      </button>
    </span>
  )
}

export function SlackWorkspaceCard({
  workspace,
  people,
  directory,
  subscriptions,
  sessions,
  busy,
  onAllowPerson,
  onDisallowPerson,
  onAddSubscription,
  onRemoveSubscription,
  onUpdateTokens,
  onDisconnect
}: {
  workspace: SlackWorkspace
  people: SlackAllowedUser[]
  directory: SlackDirectory | null
  subscriptions: SlackSubscription[]
  sessions: AgentSession[]
  busy: boolean
  onAllowPerson: (
    teamId: string,
    slackUserId: string,
    displayName?: string | null
  ) => void
  onDisallowPerson: (teamId: string, slackUserId: string) => void
  onAddSubscription: (sessionId: string, channel: string) => void
  onRemoveSubscription: (sessionId: string, channel: string) => void
  onUpdateTokens: (workspace: SlackWorkspace) => void
  onDisconnect: (teamId: string) => void
}) {
  const allowed = new Set(people.map(person => person.slackUserId))
  const knownPeople = directory?.people ?? []
  const nameById = new Map(knownPeople.map(person => [person.id, person]))

  const peopleOptions: PickerOption[] = knownPeople
    .filter(person => !allowed.has(person.id))
    .map(person => ({
      id: person.id,
      label: person.name,
      hint: person.handle ? `@${person.handle}` : null,
      avatarUrl: person.avatarUrl
    }))

  const listening = subscriptions.filter(item =>
    item.channel.startsWith(`slack:${workspace.teamId}/`)
  )
  const listeningKeys = new Set(listening.map(item => item.channel))

  const channelOptions: PickerOption[] = (directory?.channels ?? [])
    .filter(
      channel =>
        !listeningKeys.has(`slack:${workspace.teamId}/${channel.id}`)
    )
    .map(channel => ({
      id: channel.id,
      label: `#${channel.name}`,
      hint: channel.isPrivate ? 'private' : null
    }))

  const channelLabel = (channel: string) => {
    const id = channel.split('/').at(-1) ?? channel
    const known = directory?.channels.find(item => item.id === id)
    return known ? `#${known.name}` : id
  }

  return (
    <section className="border-border/70 rounded-xl border">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium">
            {workspace.teamName || workspace.teamId}
          </p>
          <p className="text-muted-foreground truncate text-[11px]">
            {workspace.domain || workspace.teamId} ·{' '}
            {workspace.mode === 'relay' ? 'relay' : 'socket mode'}
          </p>
        </div>
      </div>

      <Row label="People">
        <div className="flex flex-wrap items-center gap-1.5">
          {people.map(person => {
            const known = nameById.get(person.slackUserId)
            return (
              <Chip
                key={person.slackUserId}
                id={person.slackUserId}
                name={known?.name || person.displayName || person.slackUserId}
                avatarUrl={known?.avatarUrl}
                disabled={busy}
                onRemove={() =>
                  onDisallowPerson(workspace.teamId, person.slackUserId)
                }
              />
            )
          })}
          <SlackPickerPopover
            label="Add person"
            placeholder="Type a name…"
            emptyHint="No people found. The bot may still be loading the directory."
            options={peopleOptions}
            disabled={busy}
            showAvatars
            onPick={option =>
              onAllowPerson(workspace.teamId, option.id, option.label)
            }
          />
        </div>
        {people.length === 0 ? (
          <p className="text-muted-foreground mt-1.5 text-[11px]">
            Nobody can trigger the agent yet. Mentions from unlisted people wait
            for your OK.
          </p>
        ) : null}
      </Row>

      <Row label="Listening">
        <div className="space-y-1.5">
          {listening.map(item => {
            const session = sessions.find(entry => entry.id === item.sessionId)
            return (
              <div
                key={`${item.sessionId}:${item.channel}`}
                className="flex items-center gap-2 text-[12px]"
              >
                <span className="max-w-52 truncate font-medium">
                  {session?.title || item.sessionId}
                </span>
                <span className="text-muted-foreground">←</span>
                <span className="text-muted-foreground truncate">
                  {channelLabel(item.channel)}
                </span>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    onRemoveSubscription(item.sessionId, item.channel)
                  }
                  aria-label="Stop listening"
                  className="text-muted-foreground hover:text-foreground ml-auto disabled:opacity-40"
                >
                  <X className="size-3.5" />
                </button>
              </div>
            )
          })}

          <SlackChannelAdder
            busy={busy}
            sessions={sessions}
            channelOptions={channelOptions}
            onAdd={onAddSubscription}
          />
        </div>
      </Row>

      <div className="border-border/70 flex items-center justify-between border-t px-4 py-2.5">
        <Button
          size="sm"
          variant="ghost"
          className="h-7 gap-1.5 text-[12px]"
          disabled={busy}
          onClick={() => onUpdateTokens(workspace)}
        >
          <RefreshCw className="size-3.5" />
          Update tokens
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="text-destructive h-7 text-[12px]"
          disabled={busy}
          onClick={() => onDisconnect(workspace.teamId)}
        >
          Disconnect workspace
        </Button>
      </div>
    </section>
  )
}

function SlackChannelAdder({
  busy,
  sessions,
  channelOptions,
  onAdd
}: {
  busy: boolean
  sessions: AgentSession[]
  channelOptions: PickerOption[]
  onAdd: (sessionId: string, channel: string) => void
}) {
  // A channel only listens on behalf of a session, so pick that first.
  const [sessionId, setSessionId] = useState('')

  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
      <select
        value={sessionId}
        onChange={event => setSessionId(event.target.value)}
        className="border-border bg-background h-7 max-w-48 rounded-md border px-2 text-[12px]"
      >
        <option value="">Pick a session…</option>
        {sessions.slice(0, 40).map(session => (
          <option key={session.id} value={session.id}>
            {session.title}
          </option>
        ))}
      </select>
      <SlackPickerPopover
        label="Add channel"
        placeholder="Search channels…"
        emptyHint="No channels found. Invite the bot to a channel first."
        options={channelOptions}
        disabled={busy || !sessionId}
        onPick={option => onAdd(sessionId, option.id)}
      />
    </div>
  )
}
