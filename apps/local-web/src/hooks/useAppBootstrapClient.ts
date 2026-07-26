import { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useMemo, useState } from 'react'

import {
  normalizeBackendUrl,
  readStoredBackendUrl
} from '@/lib/backend-url'
import { readRememberedApiKey } from '@/lib/remembered-auth'

export function useAppBootstrapClient() {
  const [backendUrl, setBackendUrlState] = useState(readStoredBackendUrl)
  const setBackendUrl = (value: string) => {
    setBackendUrlState(normalizeBackendUrl(value))
  }
  const [backendApiKey, setBackendApiKey] = useState('')
  // Cookie sessions do not stick in the Tauri shell (cross-origin). Restore the
  // remembered Authorization key so quit/reopen does not force login again.
  const [clientApiKey, setClientApiKey] = useState<string | undefined>(() =>
    readRememberedApiKey(readStoredBackendUrl())
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
