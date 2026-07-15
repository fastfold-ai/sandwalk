import { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useMemo, useState } from 'react'

import {
  normalizeBackendUrl,
  readStoredBackendUrl
} from '@/lib/backend-url'

export function useAppBootstrapClient() {
  const [backendUrl, setBackendUrlState] = useState(readStoredBackendUrl)
  const setBackendUrl = (value: string) => {
    setBackendUrlState(normalizeBackendUrl(value))
  }
  const [backendApiKey, setBackendApiKey] = useState('')
  const [clientApiKey, setClientApiKey] = useState<string | undefined>()
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
