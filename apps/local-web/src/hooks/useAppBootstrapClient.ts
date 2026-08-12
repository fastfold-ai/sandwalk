import {
  LocalAgentClient,
  readSessionToken
} from '@sandwalk/agent-local-client'
import { useMemo, useState } from 'react'

import {
  injectedDesktopApiKeyFor,
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
    () => injectedDesktopApiKeyFor(initialUrl) || ''
  )
  // Cookie sessions do not stick in the Tauri shell (cross-origin). Prefer the
  // window inject key for *this* URL, then remembered Authorization.
  const [clientApiKey, setClientApiKey] = useState<string | undefined>(() =>
    injectedDesktopApiKeyFor(initialUrl) || readRememberedApiKey(initialUrl)
  )
  const client = useMemo(
    () =>
      new LocalAgentClient({
        baseUrl: backendUrl,
        apiKey: clientApiKey || backendApiKey || undefined,
        sessionToken: readSessionToken(backendUrl)
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
