import type { ReactNode } from 'react'

import { BackendConnectFields } from '@/components/agents/BackendConnectFields'
import { ErrorPage } from '@/components/ErrorPage'
import { SandwalkMark } from '@/components/SandwalkMark'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Button } from '@/components/ui/button'

/** WelcomeHome-aligned connect form for a remote (or non-local) agent backend. */
export function RemoteBackendConnectForm({
  backendUrl,
  setBackendUrl,
  backendApiKey,
  setBackendApiKey,
  connecting,
  connect,
  connectError,
  onDismiss,
  dismissLabel = 'Close',
  urlAutoFocus = false,
  footer
}: {
  backendUrl: string
  setBackendUrl: (value: string) => void
  backendApiKey: string
  setBackendApiKey: (value: string) => void
  connecting: boolean
  connect: () => void | Promise<void>
  connectError?: unknown | null
  onDismiss?: () => void
  dismissLabel?: string
  urlAutoFocus?: boolean
  footer?: ReactNode
}) {
  return (
    <main className="bg-background relative grid h-full place-items-center overflow-auto p-8">
      <ThemeToggle placement="top-right" />
      <div className="flex w-full max-w-md flex-col gap-10">
        <div className="flex flex-col items-center gap-3 text-center">
          <SandwalkMark className="text-foreground h-12 w-12" />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">sandwalk</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              Connect to an agent backend
            </p>
          </div>
        </div>

        <form
          className="flex flex-col gap-3"
          onSubmit={event => {
            event.preventDefault()
            void connect()
          }}
        >
          <BackendConnectFields
            backendUrl={backendUrl}
            setBackendUrl={setBackendUrl}
            backendApiKey={backendApiKey}
            setBackendApiKey={setBackendApiKey}
            connecting={connecting}
            urlAutoFocus={urlAutoFocus}
          />
          {connectError ? (
            <ErrorPage
              className="mt-1"
              variant="inline"
              error={connectError}
            />
          ) : null}
          {onDismiss ? (
            <Button
              type="button"
              variant="ghost"
              className="text-muted-foreground w-full"
              disabled={connecting}
              onClick={onDismiss}
            >
              {dismissLabel}
            </Button>
          ) : null}
          {footer}
        </form>
      </div>
    </main>
  )
}
