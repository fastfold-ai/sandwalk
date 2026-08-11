import { Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

export function BackendConnectFields({
  backendUrl,
  setBackendUrl,
  backendApiKey,
  setBackendApiKey,
  connecting,
  submitLabel = 'Connect',
  urlAutoFocus = false
}: {
  backendUrl: string
  setBackendUrl: (value: string) => void
  backendApiKey: string
  setBackendApiKey: (value: string) => void
  connecting: boolean
  submitLabel?: string
  urlAutoFocus?: boolean
}) {
  return (
    <>
      <Input
        value={backendUrl}
        onChange={event => setBackendUrl(event.target.value)}
        placeholder="http://192.168.1.10:8787"
        autoFocus={urlAutoFocus}
        autoComplete="url"
        spellCheck={false}
      />
      <Input
        className="mt-2"
        type="password"
        value={backendApiKey}
        onChange={event => setBackendApiKey(event.target.value)}
        placeholder="API key (if the server requires auth)"
        autoComplete="off"
      />
      <Button className="mt-4 w-full" disabled={connecting} type="submit">
        {connecting ? <Loader2 className="animate-spin" /> : null}
        {submitLabel}
      </Button>
    </>
  )
}
