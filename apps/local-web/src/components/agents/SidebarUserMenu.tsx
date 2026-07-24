import {
  BookOpen,
  ExternalLink,
  LogOut,
  Monitor,
  Moon,
  Settings,
  Sun
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import {
  listenSubtitle,
  SandwalkServerCard
} from '@/components/agents/SandwalkServerCard'
import { ThemeAppearanceMenuContent } from '@/components/ThemeAppearanceMenu'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { openInSystemBrowser } from '@/lib/desktop'
import {
  getStoredPalette,
  getStoredTheme,
  PALETTE_CHANGE_EVENT,
  previewPalette,
  THEME_CHANGE_EVENT,
  THEME_PALETTES,
  type ThemeMode,
  type ThemePaletteId
} from '@/lib/theme'

const DOCS_URL = 'https://docs.fastfold.ai'
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
  backendVersion = null,
  backendUrl = null,
  connected = false
}: {
  userName: string | null
  onLogout?: () => void | Promise<void>
  onRefreshUser?: () => void | Promise<void>
  backendVersion?: string | null
  backendUrl?: string | null
  connected?: boolean
}) {
  const navigate = useNavigate()
  const displayName = userName?.trim() || 'Local User'
  const [theme, setTheme] = useState<ThemeMode>(() => getStoredTheme())
  const [palette, setPalette] = useState<ThemePaletteId>(() =>
    getStoredPalette()
  )
  const [loggingOut, setLoggingOut] = useState(false)
  const serverSubtitle = useMemo(
    () =>
      listenSubtitle({
        running: connected,
        backendUrl
      }),
    [backendUrl, connected]
  )

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
  const activePalette =
    THEME_PALETTES.find(item => item.id === palette) ?? THEME_PALETTES[0]

  const ModeIcon =
    theme === 'light' ? Sun : theme === 'dark' ? Moon : Monitor

  return (
    <DropdownMenu
      onOpenChange={open => {
        if (open) void onRefreshUser?.()
      }}
    >
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="hover:bg-muted/60 data-[state=open]:bg-muted flex w-full items-center gap-2.5 rounded-lg px-2 py-2 text-left transition-colors"
        >
          <span className="bg-muted text-foreground inline-flex size-6 shrink-0 items-center justify-center rounded-full text-[10px] font-medium">
            {initials}
          </span>
          <span className="break-all text-sm font-medium">{displayName}</span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        className="bg-card min-w-[300px] rounded-xl border p-1.5 shadow-xl"
        side="top"
        align="start"
        sideOffset={10}
        onCloseAutoFocus={() => previewPalette(getStoredPalette())}
      >
        <DropdownMenuItem
          className="cursor-pointer items-start rounded-lg p-2 [&>div]:w-full"
          onClick={() => navigate('/dashboard/general')}
        >
          <SandwalkServerCard
            compact
            flat
            title={displayName}
            version={backendVersion}
            running={connected}
            subtitle={serverSubtitle}
            trailing={<Settings className="size-3.5" />}
          />
        </DropdownMenuItem>
        <DropdownMenuSeparator />

        <DropdownMenuGroup>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger className="flex cursor-default items-center gap-2 px-2.5 py-1.5 text-sm">
              <span className="flex-1">Theme</span>
              <span className="text-muted-foreground flex items-center gap-1.5 text-xs">
                <ModeIcon className="size-3.5 shrink-0" />
                <span className="flex items-center gap-0.5">
                  {activePalette.swatches.map(color => (
                    <span
                      key={color}
                      className="border-border/60 size-2.5 rounded-sm border"
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </span>
                <span className="max-w-[4.5rem] truncate">
                  {activePalette.name}
                </span>
              </span>
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent
              sideOffset={8}
              collisionPadding={16}
              className="bg-card max-h-[min(28rem,calc(100dvh-2rem))] w-64 overflow-y-auto rounded-xl border p-1.5 shadow-xl"
              onPointerLeave={() => previewPalette(getStoredPalette())}
            >
              <ThemeAppearanceMenuContent
                mode={theme}
                palette={palette}
                onPreviewPalette={previewPalette}
              />
            </DropdownMenuSubContent>
          </DropdownMenuSub>
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
            onClick={() => openExternal(CLOUD_URL)}
          >
            <span>Fastfold Cloud</span>
            <img
              src="/ff_simbol_color.svg"
              alt=""
              aria-hidden="true"
              className="size-4"
            />
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
          disabled={loggingOut || !onLogout}
          onClick={() => {
            if (!onLogout) return
            setLoggingOut(true)
            void Promise.resolve(onLogout()).finally(() => setLoggingOut(false))
          }}
        >
          <span>{loggingOut ? 'Signing out…' : 'Log out'}</span>
          <LogOut className="text-muted-foreground size-4" />
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
