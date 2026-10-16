import {
  ChevronRight,
  ExternalLink,
  LayoutDashboard,
  LogOut,
  Settings
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useLocation, useNavigate } from 'react-router-dom'

import { ThemeAppearanceMenuContent } from '@/components/ThemeAppearanceMenu'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { useDesktopUpdate } from '@/hooks/useDesktopUpdate'
import { openInSystemBrowser } from '@/lib/desktop'
import {
  getStoredPalette,
  getStoredTheme,
  PALETTE_CHANGE_EVENT,
  previewPalette,
  THEME_CHANGE_EVENT,
  type ThemeMode,
  type ThemePaletteId
} from '@/lib/theme'
import { cn } from '@/lib/utils'

const CLOUD_URL = 'https://cloud.fastfold.ai'
const STATUS_URL = 'https://status.fastfold.ai'

function userInitials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return 'FF'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase()
}

function openExternal(url: string) {
  void openInSystemBrowser(url)
}

export function SidebarUserMenu({
  userName,
  onLogout,
  onRefreshUser,
  backendVersion: _backendVersion = null,
  backendUrl: _backendUrl = null,
  connected: _connected = false
}: {
  userName: string | null
  onLogout?: () => void | Promise<void>
  onRefreshUser?: () => void | Promise<void>
  backendVersion?: string | null
  backendUrl?: string | null
  connected?: boolean
}) {
  const navigate = useNavigate()
  const settingsActive = useLocation().pathname.startsWith('/dashboard')
  const update = useDesktopUpdate()
  const displayName = userName?.trim() || 'Local User'
  const [theme, setTheme] = useState<ThemeMode>(() => getStoredTheme())
  const [palette, setPalette] = useState<ThemePaletteId>(() =>
    getStoredPalette()
  )
  const [loggingOut, setLoggingOut] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [themeOpen, setThemeOpen] = useState(false)
  const themeRowRef = useRef<HTMLDivElement | null>(null)
  const themeCloseTimer = useRef<number | null>(null)
  const [themePos, setThemePos] = useState<{
    top: number
    left: number
    maxHeight: number
  } | null>(null)

  useEffect(() => {
    const onTheme = (event: Event) => {
      setTheme((event as CustomEvent<ThemeMode>).detail)
    }
    const onPalette = (event: Event) => {
      setPalette((event as CustomEvent<ThemePaletteId>).detail)
    }
    window.addEventListener(THEME_CHANGE_EVENT, onTheme)
    window.addEventListener(PALETTE_CHANGE_EVENT, onPalette)
    return () => {
      window.removeEventListener(THEME_CHANGE_EVENT, onTheme)
      window.removeEventListener(PALETTE_CHANGE_EVENT, onPalette)
    }
  }, [])

  const initials = useMemo(() => userInitials(displayName), [displayName])

  const cancelThemeClose = () => {
    if (themeCloseTimer.current != null) {
      window.clearTimeout(themeCloseTimer.current)
      themeCloseTimer.current = null
    }
  }
  const scheduleThemeClose = () => {
    cancelThemeClose()
    themeCloseTimer.current = window.setTimeout(() => setThemeOpen(false), 400)
  }
  const showTheme = () => {
    cancelThemeClose()
    const rect = themeRowRef.current?.getBoundingClientRect()
    if (rect) {
      const width = 272
      const gap = 6
      const left =
        window.innerWidth - rect.right >= width + gap + 8
          ? rect.right + gap
          : Math.max(8, rect.left - width - gap)
      // Sit level with the Theme row. Shrink and scroll instead of
      // jumping the panel up over the rest of the sidebar.
      const top = Math.max(8, rect.top)
      const maxHeight = Math.max(160, window.innerHeight - top - 8)
      setThemePos({ top, left, maxHeight })
    }
    setThemeOpen(true)
  }
  useEffect(() => () => cancelThemeClose(), [])

  return (
    <DropdownMenu
      modal={false}
      open={menuOpen}
      onOpenChange={open => {
        setMenuOpen(open)
        if (open) void onRefreshUser?.()
        else {
          setThemeOpen(false)
          previewPalette(getStoredPalette())
        }
      }}
    >
      <div className="flex w-full items-center gap-1 px-1.5 py-1">
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={displayName}
            className="hover:bg-sidebar-accent/50 data-[state=open]:bg-sidebar-accent/55 flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-1.5 py-1.5 text-left"
          >
            <span className="bg-muted text-foreground inline-flex size-6 shrink-0 items-center justify-center rounded-full text-[10px] font-medium">
              {initials}
            </span>
            <span className="min-w-0 flex-1 truncate text-sm font-medium">
              {displayName}
            </span>
          </button>
        </DropdownMenuTrigger>
        {update.available ? (
          <button
            type="button"
            className="shrink-0 rounded-md bg-[#C6A15B] px-2 py-0.5 text-[11px] font-semibold text-[#1c1408] hover:bg-[#d4b56a] disabled:opacity-70"
            disabled={update.installing}
            onClick={() => void update.installUpdate()}
          >
            {update.installing ? 'Updating…' : 'Update'}
          </button>
        ) : null}
        <button
          type="button"
          aria-label="Settings"
          aria-current={settingsActive ? 'page' : undefined}
          className={cn(
            'inline-flex size-7 shrink-0 items-center justify-center rounded-lg',
            settingsActive
              ? 'bg-sidebar-accent/70 text-foreground'
              : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground'
          )}
          onClick={() => navigate('/dashboard/general')}
        >
          <Settings className="size-3.5" />
        </button>
      </div>
      <DropdownMenuContent
        className="sandwalk-glass-menu bg-card w-64 rounded-xl border p-1 shadow-xl"
        side="top"
        align="start"
        sideOffset={8}
        collisionPadding={12}
        onCloseAutoFocus={event => {
          event.preventDefault()
          previewPalette(getStoredPalette())
        }}
        onInteractOutside={event => {
          const target = event.target
          if (
            target instanceof Element &&
            target.closest('[data-account-theme-menu]')
          ) {
            event.preventDefault()
          }
        }}
      >
        <DropdownMenuItem
          className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-sm"
          onClick={() => navigate('/dashboard/general')}
        >
          <Settings className="text-muted-foreground size-4 shrink-0" />
          <span className="min-w-0 flex-1">Settings</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />

        <div
          ref={themeRowRef}
          className="hover:bg-accent flex cursor-default items-center gap-2 rounded-lg px-2 py-1.5 text-sm"
          onMouseEnter={showTheme}
          onMouseLeave={scheduleThemeClose}
          onClick={event => {
            event.preventDefault()
            event.stopPropagation()
            if (themeOpen) setThemeOpen(false)
            else showTheme()
          }}
        >
          <span className="min-w-0 flex-1 truncate">Theme</span>
          <ChevronRight className="size-3.5 shrink-0 opacity-60" />
        </div>
        {themeOpen && themePos
          ? createPortal(
              <div
                data-account-theme-menu
                className="fixed z-[200]"
                style={{
                  top: themePos.top,
                  left: themePos.left - 10,
                  paddingLeft: 10
                }}
                onMouseEnter={cancelThemeClose}
                onMouseLeave={scheduleThemeClose}
              >
                <div
                  className="sandwalk-glass-menu bg-popover text-popover-foreground w-[17rem] overflow-y-auto rounded-xl border p-1.5 shadow-xl"
                  style={{ maxHeight: themePos.maxHeight }}
                >
                  <ThemeAppearanceMenuContent mode={theme} palette={palette} />
                </div>
              </div>,
              document.body
            )
          : null}

        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuItem
            className="flex cursor-pointer items-center gap-2 px-2 py-1.5 text-sm"
            onClick={() => navigate('/dashboard')}
          >
            <LayoutDashboard className="text-muted-foreground size-4 shrink-0" />
            <span className="truncate">Overview</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            className="flex cursor-pointer items-center gap-2 px-2 py-1.5 text-sm"
            onClick={() => openExternal(CLOUD_URL)}
          >
            <img
              src="/ff_simbol_color.svg"
              alt=""
              aria-hidden="true"
              className="size-4 shrink-0"
            />
            <span className="truncate">Fastfold Cloud</span>
          </DropdownMenuItem>
          <DropdownMenuItem
            className="flex cursor-pointer items-center gap-2 px-2 py-1.5 text-sm"
            onClick={() => openExternal(STATUS_URL)}
          >
            <ExternalLink className="text-muted-foreground size-4 shrink-0" />
            <span className="truncate">Status</span>
          </DropdownMenuItem>
        </DropdownMenuGroup>

        <DropdownMenuSeparator />

        <DropdownMenuItem
          className="flex cursor-pointer items-center gap-2 px-2 py-1.5 text-sm"
          disabled={loggingOut || !onLogout}
          onClick={() => {
            if (!onLogout) return
            setLoggingOut(true)
            void Promise.resolve(onLogout()).finally(() => setLoggingOut(false))
          }}
        >
          <LogOut className="text-muted-foreground size-4 shrink-0" />
          <span className="truncate">
            {loggingOut ? 'Signing out…' : 'Log out'}
          </span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
