import { useEffect, useState, useCallback } from 'react'

import { DEFAULT_BACKEND_URL } from '@/lib/backend-url'

export interface OfflineStatus {
  isOffline: boolean
  reason: string | null
  message: string
  featuresAffected: string[]
  lastCheck: string | null
  targetsChecked: string[] | null
  forced: boolean
}

export function useOfflineStatus(intervalMs: number = 30000) {
  const [status, setStatus] = useState<OfflineStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchStatus = useCallback(async () => {
    const baseUrl = DEFAULT_BACKEND_URL
    try {
      const response = await fetch(`${baseUrl}/v1/system/offline-status`)
      if (!response.ok) {
        setStatus(null)
        setError(null)
        return
      }
      const data = await response.json()
      setStatus(data)
      setError(null)
    } catch {
      // Network unreachable — we're definitely offline
      setError('Could not reach server')
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    fetchStatus().finally(() => setLoading(false))
  }, [fetchStatus])

  useEffect(() => {
    const timer = setInterval(fetchStatus, intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs, fetchStatus])

  return { status, loading, error, refetch: fetchStatus }
}
