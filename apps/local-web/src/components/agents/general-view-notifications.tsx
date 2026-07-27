import { Check, ChevronDown } from 'lucide-react'
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

function CompletionModeRow({ mode }: { mode: NotifyCompletionMode }) {
  const current =
    NOTIFY_COMPLETION_OPTIONS.find(item => item.id === mode) ??
    NOTIFY_COMPLETION_OPTIONS[1]
  return (
    <div className="border-border/70 flex items-center justify-between gap-3 rounded-xl border p-4">
      <div>
        <div className="text-sm font-medium">Completion notifications</div>
        <p className="text-muted-foreground mt-0.5 text-xs">
          Notify when an agent finishes or fails a run.
        </p>
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="border-border bg-card text-foreground focus-visible:ring-ring flex h-9 min-w-48 shrink-0 items-center justify-between gap-2 rounded-md border px-3 text-sm outline-none focus-visible:ring-1"
          >
            <span className="truncate">{current.label}</span>
            <ChevronDown className="text-muted-foreground size-3.5 shrink-0" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          {NOTIFY_COMPLETION_OPTIONS.map(item => {
            const selected = item.id === mode
            return (
              <DropdownMenuItem
                key={item.id}
                onSelect={() => applyNotifyCompletion(item.id)}
                className={cn(selected && 'text-primary')}
              >
                <Check
                  className={cn('size-3.5 shrink-0', !selected && 'invisible')}
                />
                <span className="truncate">{item.label}</span>
              </DropdownMenuItem>
            )
          })}
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

function ApprovalToggleRow({ enabled }: { enabled: boolean }) {
  return (
    <div className="border-border/70 flex items-center justify-between gap-3 rounded-xl border p-4">
      <div>
        <div className="text-sm font-medium">Permission notifications</div>
        <p className="text-muted-foreground mt-0.5 text-xs">
          Notify when an agent needs your approval (e.g. installing or removing
          skills).
        </p>
      </div>
      <NotifyToggle
        enabled={enabled}
        label="Permission notifications"
        onToggle={() => applyNotifyApproval(!enabled)}
      />
    </div>
  )
}

function MacPermissionRow({
  permission,
  requesting,
  onEnable
}: {
  permission: 'granted' | 'denied' | 'default' | 'unsupported'
  requesting: boolean
  onEnable: () => void
}) {
  const statusLabel =
    permission === 'granted'
      ? 'Enabled'
      : permission === 'denied'
        ? 'Blocked in System Settings'
        : permission === 'unsupported'
          ? 'Unavailable'
          : 'Not enabled'

  return (
    <div className="border-border/70 flex items-center justify-between gap-3 rounded-xl border p-4">
      <div>
        <div className="text-sm font-medium">macOS Notification Center</div>
        <p className="text-muted-foreground mt-0.5 text-xs">
          Status: {statusLabel}. Allow Sandwalk to show banners when the app is
          in the background.
        </p>
      </div>
      {permission === 'granted' ? (
        <span className="text-muted-foreground shrink-0 text-xs font-medium">
          Allowed
        </span>
      ) : (
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={requesting || permission === 'unsupported'}
          onClick={onEnable}
        >
          {requesting ? 'Requesting…' : 'Enable'}
        </Button>
      )}
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

  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-base font-semibold">Notifications</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          macOS Notification Center alerts, a Dock badge, and a blue unread
          dot on sessions that need attention.
        </p>
      </div>

      <CompletionModeRow mode={completion} />
      <ApprovalToggleRow enabled={approval} />

      {macDesktop ? (
        <MacPermissionRow
          permission={permission}
          requesting={requesting}
          onEnable={() => void enableNative()}
        />
      ) : null}
    </section>
  )
}
