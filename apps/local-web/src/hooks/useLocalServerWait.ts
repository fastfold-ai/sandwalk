import { useEffect, useRef, useState } from 'react'

import { isBackendUnavailableError } from '@/lib/app-error'
import { isLocalBackendUrl } from '@/lib/backend-url'
import { desktopServerStatus, isTauri } from '@/lib/desktop'
import {
  LOCAL_SERVER_DOWN_RETRY_MS,
  LOCAL_SERVER_START_RETRY_MS,
  shouldShowLocalServerStarting
} from '@/lib/local-server-wait'

export function useLocalServerWait({
  backendUrl,
  connecting,
  error,
  health,
  connectionPaused,
  needsAuthLogin,
  connect
}: {
  backendUrl: string
  connecting: boolean
  error: string | null
  health: unknown
  connectionPaused: boolean
  needsAuthLogin: boolean
  connect: () => Promise<void>
}): boolean {
  const [desktopState, setDesktopState] = useState<string | null>(null)
  const [waitStartedAt, setWaitStartedAt] = useState<number | null>(null)
  const [nowMs, setNowMs] = useState(() => Date.now())
  const waitStartedAtRef = useRef<number | null>(null)

  const unavailable = Boolean(error) && isBackendUnavailableError(error)
  const localStarting = shouldShowLocalServerStarting({
    local: isLocalBackendUrl(backendUrl),
    connecting,
    unavailable,
    elapsedMs: waitStartedAt ? nowMs - waitStartedAt : 0,
    desktopState
  })

  useEffect(() => {
    if (
      connecting &&
      isLocalBackendUrl(backendUrl) &&
      waitStartedAtRef.current == null
    ) {
      waitStartedAtRef.current = Date.now()
      setWaitStartedAt(waitStartedAtRef.current)
    }
  }, [backendUrl, connecting])

  useEffect(() => {
    if (!health && !connectionPaused) return
    waitStartedAtRef.current = null
    setWaitStartedAt(null)
    setDesktopState(null)
  }, [connectionPaused, health])

  useEffect(() => {
    if (!isTauri()) return
    if (connectionPaused || health || !isLocalBackendUrl(backendUrl)) return
    let cancelled = false
    const poll = async () => {
      const status = await desktopServerStatus()
      if (cancelled || !status) return
      setDesktopState(status.state)
    }
    void poll()
    const timer = window.setInterval(() => {
      void poll()
    }, 2_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [backendUrl, connectionPaused, health])

  useEffect(() => {
    if (!localStarting || waitStartedAt == null) return
    const timer = window.setInterval(() => {
      setNowMs(Date.now())
    }, 1_000)
    return () => window.clearInterval(timer)
  }, [localStarting, waitStartedAt])

  useEffect(() => {
    if (needsAuthLogin || connectionPaused || health || connecting) return
    if (!error) return
    if (!isLocalBackendUrl(backendUrl)) return
    if (!isBackendUnavailableError(error)) return
    const timer = window.setInterval(() => {
      void connect()
    }, localStarting ? LOCAL_SERVER_START_RETRY_MS : LOCAL_SERVER_DOWN_RETRY_MS)
    return () => window.clearInterval(timer)
  }, [
    backendUrl,
    connect,
    connecting,
    connectionPaused,
    error,
    health,
    localStarting,
    needsAuthLogin
  ])

  return localStarting
}
