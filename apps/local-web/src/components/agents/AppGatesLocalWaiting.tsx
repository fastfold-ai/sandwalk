import { Loader2 } from 'lucide-react'
import { useState } from 'react'

import { BackendConnectFields } from '@/components/agents/BackendConnectFields'
import { ErrorPage } from '@/components/ErrorPage'
import { SandwalkMark } from '@/components/SandwalkMark'
import { Button } from '@/components/ui/button'
import { DEFAULT_BACKEND_URL } from '@/lib/backend-url'

export function AppGatesLocalWaiting({
  backendDown,
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
      <main className="bg-background grid h-full place-items-center p-6">
        <form
          className="bg-card w-full max-w-lg rounded-xl border p-6"
          onSubmit={event => {
            event.preventDefault()
            void connect()
          }}
        >
          <div className="mb-6 flex items-center gap-3">
            <div className="bg-primary text-primary-foreground grid size-10 place-items-center rounded-lg">
              <SandwalkMark className="h-6 w-6" />
            </div>
            <div>
              <h1 className="font-semibold">sandwalk</h1>
              <p className="text-muted-foreground text-sm">
                Connect to an agent backend
              </p>
            </div>
          </div>
          <BackendConnectFields
            backendUrl={backendUrl}
            setBackendUrl={setBackendUrl}
            backendApiKey={backendApiKey}
            setBackendApiKey={setBackendApiKey}
            connecting={connecting}
            urlAutoFocus
          />
          {connectError ? (
            <ErrorPage
              className="mt-3"
              variant="inline"
              error={connectError}
            />
          ) : null}
          <Button
            type="button"
            variant="ghost"
            className="mt-3 w-full"
            disabled={connecting}
            onClick={() => {
              setBackendUrl(DEFAULT_BACKEND_URL)
              setBackendApiKey('')
              setShowRemote(false)
            }}
          >
            Back to local server
          </Button>
        </form>
      </main>
    )
  }

  return (
    <main className="bg-background grid h-full place-items-center p-6">
      <div className="bg-card w-full max-w-md space-y-4 rounded-xl border p-6 text-center">
        <div className="flex flex-col items-center gap-3">
          <div className="bg-primary text-primary-foreground grid size-10 place-items-center rounded-lg">
            <SandwalkMark className="h-6 w-6" />
          </div>
          <div>
            <h1 className="font-semibold">sandwalk</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              {backendDown
                ? 'Local agent API error'
                : connecting
                  ? 'Waiting for the local agent API…'
                  : 'Connecting…'}
            </p>
          </div>
          {connecting && !connectError ? (
            <Loader2 className="text-muted-foreground size-5 animate-spin" />
          ) : null}
        </div>
        {connectError ? (
          <ErrorPage
            className="text-left"
            variant="inline"
            error={connectError}
            onRetry={() => void connect()}
            retryLabel="Retry"
          />
        ) : null}
        {!connectError ? (
          <Button
            className="w-full"
            disabled={connecting}
            onClick={() => void connect()}
          >
            {connecting ? <Loader2 className="animate-spin" /> : null}
            Retry
          </Button>
        ) : null}
        <Button
          type="button"
          variant="ghost"
          className="w-full"
          disabled={connecting}
          onClick={() => setShowRemote(true)}
        >
          Open remote…
        </Button>
        {onBackHome ? (
          <Button
            type="button"
            variant="ghost"
            className="w-full"
            disabled={connecting}
            onClick={onBackHome}
          >
            Back to home
          </Button>
        ) : null}
      </div>
    </main>
  )
}
