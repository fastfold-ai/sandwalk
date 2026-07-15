import { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useMemo, useState } from 'react'

const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8787'

export function useAppBootstrapClient() {
  const [backendUrl, setBackendUrl] = useState(
    () => localStorage.getItem('fastfold.backend.url') || DEFAULT_BACKEND_URL
  )
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
