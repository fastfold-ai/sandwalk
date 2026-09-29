import { useCallback, useEffect, useRef, useState } from 'react'

import { DEFAULT_BACKEND_URL, readStoredBackendUrl } from '@/lib/backend-url'

export interface OfflineStatus {
  isOffline: boolean
  justOnline: boolean
  reason: string | null
  message: string
  featuresAffected: string[]
  lastCheck: string | null
  targetsChecked: string[] | null
  forced: boolean
}

export function normalizeOfflinePayload(
  raw: Record<string, unknown>
): OfflineStatus {
  const affected = raw.featuresAffected ?? raw.features_affected
  return {
    isOffline: Boolean(raw.isOffline ?? raw.is_offline),
    justOnline: false,
    reason: typeof raw.reason === 'string' ? raw.reason : null,
    message: typeof raw.message === 'string' ? raw.message : '',
    featuresAffected: Array.isArray(affected)
      ? affected.map(item => String(item))
      : [],
    lastCheck:
      typeof raw.lastCheck === 'string'
        ? raw.lastCheck
        : typeof raw.last_check === 'string'
          ? raw.last_check
          : null,
    targetsChecked: Array.isArray(raw.targetsChecked)
      ? raw.targetsChecked.map(item => String(item))
      : Array.isArray(raw.targets_checked)
        ? raw.targets_checked.map(item => String(item))
        : null,
    forced: Boolean(raw.forced)
  }
}

export function mergeOfflineSignals(
  browserOnline: boolean,
  server: OfflineStatus | null,
  apiUnreachable: boolean
): Pick<OfflineStatus, 'isOffline' | 'message' | 'featuresAffected'> {
  const serverOffline = Boolean(server?.isOffline)
  const isOffline = !browserOnline || serverOffline || apiUnreachable
  if (!isOffline) {
    return { isOffline: false, message: 'Back online', featuresAffected: [] }
  }
  if (!browserOnline) {
    return {
      isOffline: true,
      message: 'No internet connection',
      featuresAffected: server?.featuresAffected ?? []
    }
  }
  if (apiUnreachable) {
    return {
      isOffline: true,
      message: 'Cannot reach the Sandwalk server',
      featuresAffected: []
    }
  }
  return {
    isOffline: true,
    message: server?.message || 'Offline — some features may not work',
    featuresAffected: server?.featuresAffected ?? []
  }
}

export function useOfflineStatus(intervalMs: number = 5000) {
  const [browserOnline, setBrowserOnline] = useState(() =>
    typeof navigator === 'undefined' ? true : navigator.onLine
  )
  const [server, setServer] = useState<OfflineStatus | null>(null)
  const [apiUnreachable, setApiUnreachable] = useState(false)
  const [justOnline, setJustOnline] = useState(false)
  const wasOffline = useRef(false)

  const fetchStatus = useCallback(async () => {
    if (typeof navigator !== 'undefined') {
      setBrowserOnline(navigator.onLine)
    }
    const baseUrl = readStoredBackendUrl() || DEFAULT_BACKEND_URL
    try {
      const response = await fetch(`${baseUrl}/v1/system/offline-status`, {
        credentials: 'include'
      })
      if (!response.ok) {
        setApiUnreachable(false)
        return
      }
      const data = (await response.json()) as Record<string, unknown>
      const next = normalizeOfflinePayload(data)
      // Identical payload → keep the previous object so the 5s poll does
      // not re-render the shell (and everything under it) for nothing.
      setServer(prev =>
        prev && JSON.stringify(prev) === JSON.stringify(next) ? prev : next
      )
      setApiUnreachable(false)
    } catch {
      setApiUnreachable(true)
    }
  }, [])

  useEffect(() => {
    const on = () => setBrowserOnline(true)
    const off = () => setBrowserOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])

  useEffect(() => {
    void fetchStatus()
    const timer = window.setInterval(() => void fetchStatus(), intervalMs)
    return () => window.clearInterval(timer)
  }, [fetchStatus, intervalMs])

  const merged = mergeOfflineSignals(browserOnline, server, apiUnreachable)

  useEffect(() => {
    if (merged.isOffline) {
      wasOffline.current = true
      setJustOnline(false)
      return
    }
    if (!wasOffline.current) return
    wasOffline.current = false
    setJustOnline(true)
    const timer = window.setTimeout(() => setJustOnline(false), 4000)
    return () => window.clearTimeout(timer)
  }, [merged.isOffline])

  const status: OfflineStatus = {
    ...(server || {
      isOffline: merged.isOffline,
      justOnline: false,
      reason: null,
      message: merged.message,
      featuresAffected: merged.featuresAffected,
      lastCheck: null,
      targetsChecked: null,
      forced: false
    }),
    isOffline: merged.isOffline,
    justOnline,
    message: justOnline ? 'Back online' : merged.message,
    featuresAffected: merged.featuresAffected
  }

  return { status, refetch: fetchStatus }
}
