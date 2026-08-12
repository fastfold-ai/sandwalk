import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { isLocalBackendUrl, normalizeBackendUrl } from '@/lib/backend-url'
import {
  hideDesktopWindow,
  isTauri,
  listenDesktopMenu,
  openDesktopWindow
} from '@/lib/desktop'
import { openDesktopRecent } from '@/lib/open-desktop-recent'
import { persistRememberedApiKey } from '@/lib/remembered-auth'
import { resolveBackendApiKey } from '@/lib/resolve-backend-api-key'

/**
 * File → New Window (Remote) / Open Recent + Sandwalk → Check for Updates.
 * Remote opens a dialog; Open Recent opens directly when a key is remembered,
 * otherwise opens the dialog prefilled with that URL.
 */
export function useDesktopWindowMenu(options?: {
  hideLauncherAfterOpen?: boolean
}) {
  const navigate = useNavigate()
  const [remoteOpen, setRemoteOpen] = useState(false)
  const [remoteInitialUrl, setRemoteInitialUrl] = useState<string | null>(null)
  const hideLauncherRef = useRef(Boolean(options?.hideLauncherAfterOpen))
  hideLauncherRef.current = Boolean(options?.hideLauncherAfterOpen)

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
        void openDesktopRecent({
          url: payload.url,
          route: payload.route,
          title: payload.title,
          id: payload.snapshotId,
          hostname: payload.hostname,
          platform: payload.platform
        })
          .then(result => {
            if (!result.opened) {
              setRemoteInitialUrl(result.url)
              setRemoteOpen(true)
              return
            }
            if (
              hideLauncherRef.current &&
              !isLocalBackendUrl(result.url)
            ) {
              void hideDesktopWindow().catch(() => {
                // ignore
              })
            }
          })
          .catch(() => {
            const url = normalizeBackendUrl(payload.url!)
            setRemoteInitialUrl(url)
            setRemoteOpen(true)
          })
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
    setRemoteInitialUrl,
    /** Helper for tests / future callers that already have a URL+key. */
    openRemoteWithAuth: async (url: string, apiKey?: string) => {
      const normalized = normalizeBackendUrl(url)
      const key = (await resolveBackendApiKey(normalized, apiKey)) || ''
      if (key) persistRememberedApiKey(normalized, key)
      await openDesktopWindow({
        backendUrl: normalized,
        apiKey: key || null,
        focusExisting: true
      })
    }
  }
}
