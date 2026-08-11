import { Eye, EyeOff, Loader2 } from 'lucide-react'
import { useState } from 'react'

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
  const [showKey, setShowKey] = useState(false)

  return (
    <>
      <div className="space-y-2">
        <label
          htmlFor="sandwalk-backend-url"
          className="text-muted-foreground text-xs font-medium tracking-wide uppercase"
        >
          Backend URL
        </label>
        <Input
          id="sandwalk-backend-url"
          value={backendUrl}
          onChange={event => setBackendUrl(event.target.value)}
          placeholder="http://192.168.1.10:8787"
          autoFocus={urlAutoFocus}
          autoComplete="url"
          spellCheck={false}
          className="h-11"
        />
      </div>
      <div className="space-y-2">
        <label
          htmlFor="sandwalk-backend-api-key"
          className="text-muted-foreground text-xs font-medium tracking-wide uppercase"
        >
          API key
        </label>
        <div className="relative">
          <Input
            id="sandwalk-backend-api-key"
            type={showKey ? 'text' : 'password'}
            value={backendApiKey}
            onChange={event => setBackendApiKey(event.target.value)}
            placeholder="Required if the server enforces auth"
            autoComplete="off"
            spellCheck={false}
            className="h-11 pr-10"
          />
          <button
            type="button"
            className="text-muted-foreground hover:text-foreground absolute top-1/2 right-1.5 flex size-8 -translate-y-1/2 items-center justify-center rounded-md"
            onClick={() => setShowKey(v => !v)}
            aria-label={showKey ? 'Hide API key' : 'Show API key'}
          >
            {showKey ? (
              <EyeOff className="size-4" />
            ) : (
              <Eye className="size-4" />
            )}
          </button>
        </div>
      </div>
      <Button className="mt-1 h-11 w-full" disabled={connecting} type="submit">
        {connecting ? <Loader2 className="animate-spin" /> : null}
        {submitLabel}
      </Button>
    </>
  )
}
