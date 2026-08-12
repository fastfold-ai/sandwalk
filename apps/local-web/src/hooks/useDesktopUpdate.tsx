import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState} from 'react'

import {
  checkDesktopUpdate,
  type DesktopUpdateProgress,
  desktopUpdaterAvailable,
  installDesktopUpdate} from '@/lib/desktop-updater'

const DISMISS_KEY_PREFIX = 'sandwalk.update.dismissed:'
const AUTO_CHECK_DELAY_MS = 5_000

type DesktopUpdateContextValue = {
  available: boolean
  currentVersion: string
  latestVersion: string | null
  checking: boolean
  installing: boolean
  progress: DesktopUpdateProgress | null
  error: string | null
  hasChecked: boolean
  upToDate: boolean | null
  dismissed: boolean
  checkForUpdate: (options?: { quiet?: boolean }) => Promise<void>
  installUpdate: () => Promise<void>
  dismiss: () => void
}

const DesktopUpdateContext = createContext<DesktopUpdateContextValue | null>(
  null
)

function dismissedKey(version: string): string {
  return `${DISMISS_KEY_PREFIX}${version}`
}

function readDismissed(version: string): boolean {
  try {
    return sessionStorage.getItem(dismissedKey(version)) === '1'
  } catch {
    return false
  }
}

function writeDismissed(version: string): void {
  try {
    sessionStorage.setItem(dismissedKey(version), '1')
  } catch {
    // ignore
  }
}

export function DesktopUpdateProvider({ children }: { children: ReactNode }) {
  const [checking, setChecking] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [hasChecked, setHasChecked] = useState(false)
  const [upToDate, setUpToDate] = useState<boolean | null>(null)
  const [latestVersion, setLatestVersion] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<DesktopUpdateProgress | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const checkingRef = useRef(false)
  const installingRef = useRef(false)

  const checkForUpdate = useCallback(async (options?: { quiet?: boolean }) => {
    if (!desktopUpdaterAvailable() || checkingRef.current || installingRef.current) {
      return
    }
    checkingRef.current = true
    setChecking(true)
    if (!options?.quiet) setError(null)
    try {
      const result = await checkDesktopUpdate()
      setHasChecked(true)
      if (result.kind === 'available') {
        setUpToDate(false)
        setLatestVersion(result.info.version)
        setDismissed(readDismissed(result.info.version))
        setError(null)
      } else if (result.kind === 'current') {
        setUpToDate(true)
        setLatestVersion(null)
        setDismissed(false)
        setError(null)
      } else if (result.kind === 'error' && !options?.quiet) {
        setError(result.message)
      }
    } catch (err) {
      if (!options?.quiet) {
        setError(err instanceof Error ? err.message : String(err))
      }
    } finally {
      checkingRef.current = false
      setChecking(false)
    }
  }, [])

  const installUpdate = useCallback(async () => {
    if (!desktopUpdaterAvailable() || installingRef.current) return
    installingRef.current = true
    setInstalling(true)
    setError(null)
    setProgress({ phase: 'download', received: 0, total: null })
    const result = await installDesktopUpdate({
      onProgress: next => setProgress(next)
    })
    if (!result.ok) {
      setError(result.message || 'Update failed')
      setInstalling(false)
      installingRef.current = false
      setProgress(null)
    }
    // Success relaunches the process; leave installing true until then.
  }, [])

  const dismiss = useCallback(() => {
    if (latestVersion) writeDismissed(latestVersion)
    setDismissed(true)
  }, [latestVersion])

  useEffect(() => {
    if (!desktopUpdaterAvailable()) return
    const timer = window.setTimeout(() => {
      void checkForUpdate({ quiet: true })
    }, AUTO_CHECK_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [checkForUpdate])

  const value = useMemo<DesktopUpdateContextValue>(
    () => ({
      available: upToDate === false && Boolean(latestVersion),
      currentVersion: __UI_VERSION__,
      latestVersion,
      checking,
      installing,
      progress,
      error,
      hasChecked,
      upToDate,
      dismissed,
      checkForUpdate,
      installUpdate,
      dismiss
    }),
    [
      checkForUpdate,
      checking,
      dismissed,
      error,
      hasChecked,
      installUpdate,
      installing,
      latestVersion,
      progress,
      upToDate
    ]
  )

  return (
    <DesktopUpdateContext.Provider value={value}>
      {children}
    </DesktopUpdateContext.Provider>
  )
}

const INERT_DESKTOP_UPDATE: DesktopUpdateContextValue = {
  available: false,
  currentVersion: __UI_VERSION__,
  latestVersion: null,
  checking: false,
  installing: false,
  progress: null,
  error: null,
  hasChecked: false,
  upToDate: null,
  dismissed: false,
  checkForUpdate: async () => {},
  installUpdate: async () => {},
  dismiss: () => {}
}

export function useDesktopUpdate(): DesktopUpdateContextValue {
  return useContext(DesktopUpdateContext) ?? INERT_DESKTOP_UPDATE
}
