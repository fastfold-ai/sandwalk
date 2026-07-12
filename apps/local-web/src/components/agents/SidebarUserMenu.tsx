import {
  BookOpen,
  ExternalLink,
  LogOut,
  Monitor,
  Moon,
  Settings,
  Sun
} from 'lucide-react'
import { type ReactNode, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { applyTheme, getStoredTheme, type ThemeMode } from '@/lib/theme'
import { cn } from '@/lib/utils'

const DOCS_URL = 'https://docs.fastfold.ai'
const SLACK_URL =
  'https://fastfoldcommunity.slack.com/join/shared_invite/zt-3azbiw7qv-majshu97TymCma_TwFT6mw#/shared-invite/email'
const STATUS_URL = 'https://status.fastfold.ai'

function SlackIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={className}
    >
      <path d="M5.04 15.16a1.68 1.68 0 1 1-1.68-1.68h1.68v1.68Zm.84 0a1.68 1.68 0 1 1 3.36 0v4.2a1.68 1.68 0 1 1-3.36 0v-4.2ZM8.88 5.04a1.68 1.68 0 1 1 1.68-1.68v1.68H8.88Zm0 .84a1.68 1.68 0 1 1 0 3.36h-4.2a1.68 1.68 0 1 1 0-3.36h4.2ZM18.96 8.88a1.68 1.68 0 1 1 1.68 1.68h-1.68V8.88Zm-.84 0a1.68 1.68 0 1 1-3.36 0V4.68a1.68 1.68 0 1 1 3.36 0v4.2ZM15.12 18.96a1.68 1.68 0 1 1-1.68 1.68v-1.68h1.68Zm0-.84a1.68 1.68 0 1 1 0-3.36h4.2a1.68 1.68 0 1 1 0 3.36h-4.2Z" />
    </svg>
  )
}

function userInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'FF'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase()
}

function openExternal(url: string) {
  window.open(url, '_blank', 'noopener,noreferrer')
}

export function SidebarUserMenu({ userName }: { userName: string | null }) {
  const navigate = useNavigate()
  const displayName = userName?.trim() || 'Local user'
  const [theme, setTheme] = useState<ThemeMode>(() => getStoredTheme())

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  useEffect(() => {
    if (theme !== 'system') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => applyTheme('system')
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [theme])

  const initials = useMemo(() => userInitials(displayName), [displayName])

  const ThemeButton = ({
    mode,
    label,
    children
  }: {
    mode: ThemeMode
    label: string
    children: ReactNode
  }) => (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={event => {
        event.preventDefault()
        event.stopPropagation()
        setTheme(mode)
      }}
      className={cn(
        'bg-card hover:bg-muted inline-flex size-7 items-center justify-center rounded-md border',
        theme === mode ? 'border-foreground/20 bg-muted' : 'border-border'
      )}
    >
      {children}
    </button>
  )

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="hover:bg-muted/60 data-[state=open]:bg-muted flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left transition-colors"
        >
          <span className="bg-muted text-foreground inline-flex size-6 shrink-0 items-center justify-center rounded-full text-[10px] font-medium">
            {initials}
          </span>
          <span className="truncate text-sm font-medium">{displayName}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="bg-card min-w-[300px] rounded-xl border p-1.5 shadow-xl"
        side="top"
        align="start"
        sideOffset={10}
      >
        <DropdownMenuItem
          className="cursor-pointer px-3 py-2"
          onClick={() => navigate('/dashboard/general')}
        >
          <div className="flex w-full items-center gap-2">
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold leading-tight">
                {displayName}
              </div>
              <div className="text-muted-foreground truncate text-xs">
                Local agent
              </div>
            </div>
            <Settings className="text-muted-foreground size-4" />
          </div>
        </DropdownMenuItem>
        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuItem
            onSelect={event => event.preventDefault()}
            className="flex items-center justify-between px-2.5 py-1.5 text-sm"
          >
            <span>Theme</span>
            <span className="flex items-center gap-2">
              <ThemeButton mode="light" label="Light theme">
                <Sun className="size-3.5" />
              </ThemeButton>
              <ThemeButton mode="system" label="System theme">
                <Monitor className="size-3.5" />
              </ThemeButton>
              <ThemeButton mode="dark" label="Dark theme">
                <Moon className="size-3.5" />
              </ThemeButton>
            </span>
          </DropdownMenuItem>
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuItem
            className="flex cursor-pointer items-center justify-between px-2.5 py-1.5 text-sm"
            onClick={() => openExternal(DOCS_URL)}
          >
            <span>Docs</span>
            <BookOpen className="text-muted-foreground size-4" />
          </DropdownMenuItem>
          <DropdownMenuItem
            className="flex cursor-pointer items-center justify-between px-2.5 py-1.5 text-sm"
            onClick={() => openExternal(SLACK_URL)}
          >
            <span>Join Slack</span>
            <SlackIcon className="text-muted-foreground size-4" />
          </DropdownMenuItem>
          <DropdownMenuItem
            className="flex cursor-pointer items-center justify-between px-2.5 py-1.5 text-sm"
            onClick={() => openExternal(STATUS_URL)}
          >
            <span>Status</span>
            <ExternalLink className="text-muted-foreground size-4" />
          </DropdownMenuItem>
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        <DropdownMenuItem
          className="flex cursor-pointer items-center justify-between px-2.5 py-1.5 text-sm"
          onClick={() => navigate('/')}
        >
          <span>Log out</span>
          <LogOut className="text-muted-foreground size-4" />
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
