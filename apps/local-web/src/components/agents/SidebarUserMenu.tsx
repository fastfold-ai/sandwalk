import {
  BookOpen,
  Check,
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
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger
} from '@/components/ui/tooltip'
import {
  listenSubtitle,
  SandwalkServerCard
} from '@/components/agents/SandwalkServerCard'
import {
  applyPalette,
  applyTheme,
  getStoredPalette,
  getStoredTheme,
  PALETTE_CHANGE_EVENT,
  previewPalette,
  THEME_CHANGE_EVENT,
  THEME_PALETTES,
  type ThemeMode,
  type ThemePaletteId
} from '@/lib/theme'
import { cn } from '@/lib/utils'

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
  window.open(url, '_blank', 'noopener,noreferrer')
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

  const ThemeButton = ({
    mode,
    label,
    children
  }: {
    mode: ThemeMode
    label: string
    children: ReactNode
  }) => (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          aria-pressed={theme === mode}
          onClick={event => {
            event.preventDefault()
            event.stopPropagation()
            applyTheme(mode)
          }}
          className={cn(
            'bg-card hover:bg-muted inline-flex h-7 flex-1 items-center justify-center rounded-md border',
            theme === mode ? 'border-foreground/20 bg-muted' : 'border-border'
          )}
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="text-xs">
        {label}
      </TooltipContent>
    </Tooltip>
  )

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
              className="bg-card w-64 rounded-xl border p-1.5 shadow-xl"
              onPointerLeave={() => previewPalette(getStoredPalette())}
            >
              <TooltipProvider delayDuration={200}>
                <div className="flex items-center gap-1.5 px-1.5 pb-1.5 pt-0.5">
                  <ThemeButton mode="light" label="Light theme">
                    <Sun className="size-3.5" />
                  </ThemeButton>
                  <ThemeButton mode="system" label="System theme">
                    <Monitor className="size-3.5" />
                  </ThemeButton>
                  <ThemeButton mode="dark" label="Dark theme">
                    <Moon className="size-3.5" />
                  </ThemeButton>
                </div>
              </TooltipProvider>
              <DropdownMenuSeparator className="my-1" />
              {THEME_PALETTES.map(item => {
                const selected = palette === item.id
                return (
                  <DropdownMenuItem
                    key={item.id}
                    className="flex cursor-pointer items-start gap-2.5 rounded-lg px-2.5 py-2"
                    onPointerEnter={() => previewPalette(item.id)}
                    onFocus={() => previewPalette(item.id)}
                    onClick={() => applyPalette(item.id)}
                  >
                    <span className="mt-0.5 flex shrink-0 items-center gap-0.5">
                      {item.swatches.map(color => (
                        <span
                          key={color}
                          className="border-border size-3 rounded-sm border"
                          style={{ backgroundColor: color }}
                        />
                      ))}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium leading-tight">
                        {item.name}
                      </span>
                      <span className="text-muted-foreground mt-0.5 block text-[11px] leading-snug">
                        {item.description}
                      </span>
                    </span>
                    {selected ? (
                      <Check className="text-foreground mt-0.5 size-3.5 shrink-0" />
                    ) : (
                      <span className="size-3.5 shrink-0" aria-hidden />
                    )}
                  </DropdownMenuItem>
                )
              })}
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
