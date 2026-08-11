import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { normalizeBackendUrl } from '@/lib/backend-url'
import {
  isTauri,
  listenDesktopMenu,
  openDesktopWindow
} from '@/lib/desktop'
import { persistRememberedApiKey, readRememberedApiKey } from '@/lib/remembered-auth'

/**
 * File → New Window (Remote) / Open Recent + Sandwalk → Check for Updates.
 * Remote opens a dialog; Open Recent opens directly when a key is remembered,
 * otherwise opens the dialog prefilled with that URL.
 */
export function useDesktopWindowMenu() {
  const navigate = useNavigate()
  const [remoteOpen, setRemoteOpen] = useState(false)
  const [remoteInitialUrl, setRemoteInitialUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!isTauri()) return
    let cancelled = false
    let unlisten: (() => void) | undefined
    void listenDesktopMenu(payload => {
      if (cancelled) return
      if (payload.action === 'new-window-remote') {
        setRemoteInitialUrl(null)
        setRemoteOpen(true)
        return
      }
      if (payload.action === 'check-updates') {
        navigate('/dashboard/general?checkUpdates=1')
        return
      }
      if (payload.action === 'open-recent' && payload.url) {
        const url = normalizeBackendUrl(payload.url)
        const key = readRememberedApiKey(url)
        const route = payload.route?.trim() || '/'
        const title = payload.title?.trim() || null
        const snapshotId = payload.snapshotId?.trim() || null
        if (key || url.includes('127.0.0.1') || url.includes('localhost')) {
          void openDesktopWindow({
            backendUrl: url,
            apiKey: key || null,
            route,
            title,
            snapshotId,
            focusExisting: true
          }).catch(() => {
            setRemoteInitialUrl(url)
            setRemoteOpen(true)
          })
          return
        }
        setRemoteInitialUrl(url)
        setRemoteOpen(true)
      }
    }).then(fn => {
      if (cancelled) fn()
      else unlisten = fn
    })
    return () => {
      cancelled = true
      unlisten?.()
    }
  }, [navigate])

  return {
    remoteOpen,
    setRemoteOpen,
    remoteInitialUrl,
    /** Helper for tests / future callers that already have a URL+key. */
    openRemoteWithAuth: async (url: string, apiKey?: string) => {
      const normalized = normalizeBackendUrl(url)
      const key = (apiKey || readRememberedApiKey(normalized) || '').trim()
      if (key) persistRememberedApiKey(normalized, key)
      await openDesktopWindow({
        backendUrl: normalized,
        apiKey: key || null,
        focusExisting: true
      })
    }
  }
}
