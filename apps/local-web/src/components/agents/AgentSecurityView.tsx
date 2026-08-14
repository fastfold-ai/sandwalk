import type { RuntimeSettings } from '@sandwalk/agent-ui-core'
import { AlertTriangle, Check, FolderLock, Globe, Loader } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type FileAccess = 'project' | 'full'

const OPTIONS: Array<{
  value: FileAccess
  label: string
  description: string
  icon: typeof FolderLock
}> = [
  {
    value: 'project',
    label: 'Project folder only',
    description:
      'The agent can read and edit files inside the session workspace and the linked project folder. Everything else on your computer is off-limits. Recommended.',
    icon: FolderLock
  },
  {
    value: 'full',
    label: 'Full filesystem access',
    description:
      'The agent can read and edit any file anywhere on your computer through shell commands and Python. Only enable this if you trust the agent to operate across your whole OS.',
    icon: Globe
  }
]

export function AgentSecurityView({
  connected,
  runtimeSettings,
  onUpdateRuntimeSettings
}: {
  connected: boolean
  runtimeSettings: RuntimeSettings | null
  onUpdateRuntimeSettings: (
    changes: Partial<RuntimeSettings>
  ) => Promise<RuntimeSettings>
}) {
  const current: FileAccess = runtimeSettings?.fileAccess === 'full'
    ? 'full'
    : 'project'
  const [selected, setSelected] = useState<FileAccess>(current)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setSelected(current)
  }, [current])

  const dirty = selected !== current

  const save = async () => {
    setSaving(true)
    setError(null)
    try {
      await onUpdateRuntimeSettings({ fileAccess: selected })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto w-full max-w-3xl space-y-8 px-4 pt-6 pb-6 md:px-6 md:pt-8 md:pb-8">
        <div>
          <h2 className="text-2xl font-semibold">Security</h2>
          <p className="text-muted-foreground mt-2 text-sm">
            Control which files the agent is allowed to read and edit during a
            session.
          </p>
        </div>

        {error ? (
          <div className="border-destructive/40 text-destructive rounded-md border px-3 py-2 text-sm">
            {error}
          </div>
        ) : null}

        <section className="space-y-3">
          <p className="text-sm font-medium">File access</p>
          <div className="space-y-3">
            {OPTIONS.map(option => {
              const active = selected === option.value
              const Icon = option.icon
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setSelected(option.value)}
                  className={cn(
                    'flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition-colors',
                    active
                      ? 'border-foreground/40 bg-muted/50'
                      : 'border-border hover:bg-muted/30'
                  )}
                >
                  <span
                    className={cn(
                      'mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg',
                      active
                        ? 'bg-foreground text-background'
                        : 'bg-muted text-muted-foreground'
                    )}
                  >
                    <Icon className="size-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="text-sm font-medium">
                        {option.label}
                      </span>
                      {option.value === 'project' ? (
                        <span className="bg-muted text-muted-foreground rounded-full px-2 py-0.5 text-[10px] font-medium">
                          Default
                        </span>
                      ) : null}
                    </span>
                    <span className="text-muted-foreground mt-1 block text-xs leading-relaxed">
                      {option.description}
                    </span>
                  </span>
                  <span
                    className={cn(
                      'mt-1 flex size-4 shrink-0 items-center justify-center rounded-full border',
                      active
                        ? 'border-foreground bg-foreground text-background'
                        : 'border-muted-foreground/40'
                    )}
                  >
                    {active ? <Check className="size-3" /> : null}
                  </span>
                </button>
              )
            })}
          </div>
        </section>

        {selected === 'full' ? (
          <div className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-amber-950 dark:text-amber-100">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" />
            <div className="text-xs leading-relaxed">
              <p className="font-medium">
                Full filesystem access is a security risk.
              </p>
              <p className="mt-1">
                With this enabled the agent can modify or delete any file your
                user account can reach — including system and config files
                outside this project. Only turn it on if you understand the
                consequences and trust what the agent will do.
              </p>
            </div>
          </div>
        ) : null}

        <p className="text-muted-foreground text-xs">
          CLI equivalent:{' '}
          <code className="bg-muted rounded px-1 py-0.5 font-mono">
            sandwalk config set agent.file_access {selected}
          </code>
          .
        </p>

        <div className="flex justify-end pt-2">
          <Button
            size="sm"
            disabled={!connected || saving || !dirty}
            onClick={() => void save()}
          >
            {saving ? <Loader className="animate-spin" /> : <Check />}
            Save
          </Button>
        </div>
      </div>
    </ScrollArea>
  )
}
