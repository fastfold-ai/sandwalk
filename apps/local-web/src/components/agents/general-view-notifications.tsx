import { Check, ChevronDown } from 'lucide-react'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import {
  getNotificationPermission,
  requestNotificationPermission
} from '@/lib/browser-notifications'
import { isMacDesktopOverlay, isTauri, platformOS } from '@/lib/desktop'
import {
  applyNotifyApproval,
  applyNotifyCompletion,
  getStoredNotifyApproval,
  getStoredNotifyCompletion,
  NOTIFY_APPROVAL_CHANGE_EVENT,
  NOTIFY_COMPLETION_CHANGE_EVENT,
  NOTIFY_COMPLETION_OPTIONS,
  type NotifyCompletionMode
} from '@/lib/notification-settings'
import { cn } from '@/lib/utils'

function isMacDesktop() {
  return isMacDesktopOverlay() || (isTauri() && platformOS() === 'macos')
}

function NotifyToggle({
  enabled,
  label,
  onToggle
}: {
  enabled: boolean
  label: string
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        enabled
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700'
      )}
      onClick={event => {
        event.preventDefault()
        onToggle()
      }}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          enabled ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </button>
  )
}

function SettingsRow({
  label,
  description,
  children
}: {
  label: string
  description: string
  children: ReactNode
}) {
  return (
    <div className="flex items-center justify-between gap-6 py-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{label}</p>
        <p className="text-muted-foreground mt-0.5 text-xs leading-snug">
          {description}
        </p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}

export function GeneralViewNotificationsSection() {
  const [completion, setCompletion] = useState<NotifyCompletionMode>(() =>
    getStoredNotifyCompletion()
  )
  const [approval, setApproval] = useState(() => getStoredNotifyApproval())
  const [macDesktop, setMacDesktop] = useState(() => isMacDesktop())
  const [permission, setPermission] = useState<
    'granted' | 'denied' | 'default' | 'unsupported'
  >('default')
  const [requesting, setRequesting] = useState(false)

  useEffect(() => {
    setMacDesktop(isMacDesktop())
    const onCompletion = (event: Event) => {
      setCompletion((event as CustomEvent<NotifyCompletionMode>).detail)
    }
    const onApproval = (event: Event) => {
      setApproval((event as CustomEvent<boolean>).detail)
    }
    window.addEventListener(NOTIFY_COMPLETION_CHANGE_EVENT, onCompletion)
    window.addEventListener(NOTIFY_APPROVAL_CHANGE_EVENT, onApproval)
    return () => {
      window.removeEventListener(NOTIFY_COMPLETION_CHANGE_EVENT, onCompletion)
      window.removeEventListener(NOTIFY_APPROVAL_CHANGE_EVENT, onApproval)
    }
  }, [])

  useEffect(() => {
    if (!macDesktop) return
    let cancelled = false
    void getNotificationPermission().then(next => {
      if (!cancelled) setPermission(next)
    })
    return () => {
      cancelled = true
    }
  }, [macDesktop])

  const enableNative = async () => {
    setRequesting(true)
    try {
      setPermission(await requestNotificationPermission())
    } finally {
      setRequesting(false)
    }
  }

  const current =
    NOTIFY_COMPLETION_OPTIONS.find(item => item.id === completion) ??
    NOTIFY_COMPLETION_OPTIONS[1]

  const macStatus =
    permission === 'granted'
      ? 'Allowed'
      : permission === 'denied'
        ? 'Blocked in System Settings'
        : permission === 'unsupported'
          ? 'Unavailable'
          : 'Not enabled'

  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-base font-semibold">Notifications</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          Alerts, Dock badge, and unread dots on sessions that need attention.
        </p>
      </div>

      <div className="divide-border/60 border-border/60 divide-y border-y">
        <SettingsRow
          label="Completion notifications"
          description="Banner when a chat finishes. Default: any chat you are not looking at, including Slack and background runs."
        >
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="border-border bg-card text-foreground focus-visible:ring-ring flex h-8 min-w-[8.5rem] shrink-0 items-center justify-between gap-2 rounded-md border px-3 text-sm outline-none focus-visible:ring-1"
              >
                <span className="truncate">{current.label}</span>
                <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {NOTIFY_COMPLETION_OPTIONS.map(item => {
                const selected = item.id === completion
                return (
                  <DropdownMenuItem
                    key={item.id}
                    onSelect={() => applyNotifyCompletion(item.id)}
                    className={cn(selected && 'text-primary')}
                  >
                    <Check
                      className={cn(
                        'size-3.5 shrink-0',
                        !selected && 'invisible'
                      )}
                    />
                    <span className="truncate">{item.label}</span>
                  </DropdownMenuItem>
                )
              })}
            </DropdownMenuContent>
          </DropdownMenu>
        </SettingsRow>

        <SettingsRow
          label="Permission notifications"
          description="Notify when an agent needs approval (e.g. installing skills)."
        >
          <NotifyToggle
            enabled={approval}
            label="Permission notifications"
            onToggle={() => applyNotifyApproval(!approval)}
          />
        </SettingsRow>

        {macDesktop ? (
          <SettingsRow
            label="macOS Notification Center"
            description={`Status: ${macStatus}. Allow banners when the app is in the background.`}
          >
            {permission === 'granted' ? (
              <span className="text-muted-foreground text-xs font-medium">
                Allowed
              </span>
            ) : (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="min-w-[8.5rem]"
                disabled={requesting || permission === 'unsupported'}
                onClick={() => void enableNative()}
              >
                {requesting ? 'Requesting…' : 'Enable'}
              </Button>
            )}
          </SettingsRow>
        ) : null}
      </div>
    </section>
  )
}
