import { Loader2 } from 'lucide-react'
import { useState } from 'react'

import { RemoteBackendConnectForm } from '@/components/agents/RemoteBackendConnectForm'
import { ErrorPage } from '@/components/ErrorPage'
import { SandwalkMark } from '@/components/SandwalkMark'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'
import { DEFAULT_BACKEND_URL } from '@/lib/backend-url'

export function AppGatesLocalWaiting({
  backendDown,
  starting,
  connecting,
  connectError,
  connect,
  backendUrl,
  setBackendUrl,
  backendApiKey,
  setBackendApiKey,
  onBackHome
}: {
  backendDown: boolean
  starting?: boolean
  connecting: boolean
  connectError: unknown | null
  connect: () => void | Promise<void>
  backendUrl: string
  setBackendUrl: (value: string) => void
  backendApiKey: string
  setBackendApiKey: (value: string) => void
  onBackHome?: () => void
}) {
  const [showRemote, setShowRemote] = useState(false)

  if (showRemote) {
    return (
      <RemoteBackendConnectForm
        backendUrl={backendUrl}
        setBackendUrl={setBackendUrl}
        backendApiKey={backendApiKey}
        setBackendApiKey={setBackendApiKey}
        connecting={connecting}
        connect={connect}
        connectError={connectError}
        urlAutoFocus
        onDismiss={() => {
          setBackendUrl(DEFAULT_BACKEND_URL)
          setBackendApiKey('')
          setShowRemote(false)
        }}
        dismissLabel="Back to local server"
      />
    )
  }

  return (
    <main className="bg-background relative grid h-full place-items-center overflow-auto p-8">
      <ThemeToggle placement="top-right" />
      <div className="flex w-full max-w-md flex-col items-stretch gap-10">
        <div className="flex flex-col items-center gap-3 text-center">
          <SandwalkMark className="text-foreground h-12 w-12" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">sandwalk</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              {starting
                ? 'Server is starting. Please wait.'
                : backendDown
                  ? 'Local agent API error'
                  : connecting
                    ? 'Waiting for the local agent API…'
                    : 'Connecting…'}
            </p>
          </div>
          {starting || (connecting && !connectError) ? (
            <Loader2 className="text-muted-foreground size-5 animate-spin" />
          ) : null}
        </div>

        <div className="flex flex-col gap-3">
          {starting ? null : connectError ? (
            <ErrorPage
              variant="inline"
              error={connectError}
              onRetry={() => void connect()}
              retryLabel="Retry"
            />
          ) : (
            <Button
              className="w-full"
              disabled={connecting}
              onClick={() => void connect()}
            >
              {connecting ? <Loader2 className="animate-spin" /> : null}
              Retry
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            className="text-muted-foreground w-full"
            disabled={connecting && !starting}
            onClick={() => setShowRemote(true)}
          >
            Open remote
          </Button>
          {onBackHome ? (
            <Button
              type="button"
              variant="ghost"
              className="text-muted-foreground w-full"
              disabled={connecting && !starting}
              onClick={onBackHome}
            >
              Back to home
            </Button>
          ) : null}
        </div>
      </div>
    </main>
  )
}
