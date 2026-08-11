import { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useMemo, useState } from 'react'

import {
  injectedDesktopApiKey,
  normalizeBackendUrl,
  readStoredBackendUrl
} from '@/lib/backend-url'
import { readRememberedApiKey } from '@/lib/remembered-auth'

export function useAppBootstrapClient() {
  const [backendUrl, setBackendUrlState] = useState(readStoredBackendUrl)
  const setBackendUrl = (value: string) => {
    setBackendUrlState(normalizeBackendUrl(value))
  }
  const initialUrl = readStoredBackendUrl()
  const [backendApiKey, setBackendApiKey] = useState(
    () => injectedDesktopApiKey() || ''
  )
  // Cookie sessions do not stick in the Tauri shell (cross-origin). Prefer the
  // window inject key, then remembered Authorization for this backend URL.
  const [clientApiKey, setClientApiKey] = useState<string | undefined>(() =>
    injectedDesktopApiKey() || readRememberedApiKey(initialUrl)
  )
  const client = useMemo(
    () =>
      new LocalAgentClient({
        baseUrl: backendUrl,
        apiKey: clientApiKey || backendApiKey || undefined
      }),
    [backendApiKey, backendUrl, clientApiKey]
  )

  return {
    backendUrl,
    setBackendUrl,
    backendApiKey,
    setBackendApiKey,
    clientApiKey,
    setClientApiKey,
    client
  }
}
