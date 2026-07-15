import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { BackendHealth } from '@sandwalk/agent-ui-core'
import type { ReactElement } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { AppGatesLocalWaiting } from '@/components/agents/AppGatesLocalWaiting'
import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { BackendConnectFields } from '@/components/agents/BackendConnectFields'
import { LoginView } from '@/components/agents/LoginView'
import { OnboardingWizardHost } from '@/components/agents/OnboardingWizardHost'
import { ErrorPage } from '@/components/ErrorPage'
import { SandwalkMark } from '@/components/SandwalkMark'
import { isBackendUnavailableError } from '@/lib/app-error'
import { isLocalBackendUrl } from '@/lib/backend-url'
import {
  clampOnboardingStep,
  ONBOARDING_MAX_STEP,
  onboardingPath
} from '@/lib/onboarding'

type AppGatesProps = {
  authBootstrapped: boolean
  needsAuthLogin: boolean
  authLoggingIn: boolean
  connecting: boolean
  authLoginError: unknown | null
  setAuthLoginError: (value: unknown | null) => void
  connect: () => void | Promise<void>
  submitAuthLogin: (apiKey: string, remember: boolean) => void | Promise<void>
  changeBackend: (url: string, apiKey?: string) => void | Promise<void>
  health: BackendHealth | null
  backendUrl: string
  setBackendUrl: (value: string) => void
  backendApiKey: string
  setBackendApiKey: (value: string) => void
  error: string | null
  errorStack: string | null
  onOnboardingPath: boolean
  onboardingStep: number
  client: LocalAgentClient
  navigate: NavigateFunction
  loadModelOptions: () => void | Promise<void>
  loadIntegrations: () => void | Promise<void>
  loadSkills: () => void | Promise<void>
  loadMcpServers: () => void | Promise<void>
  loadMcpCatalog: () => void | Promise<void>
}

export function AppGates({
  authBootstrapped,
  needsAuthLogin,
  authLoggingIn,
  connecting,
  authLoginError,
  setAuthLoginError,
  connect,
  submitAuthLogin,
  changeBackend,
  health,
  backendUrl,
  setBackendUrl,
  backendApiKey,
  setBackendApiKey,
  error,
  errorStack,
  onOnboardingPath,
  onboardingStep,
  client,
  navigate,
  loadModelOptions,
  loadIntegrations,
  loadSkills,
  loadMcpServers,
  loadMcpCatalog
}: AppGatesProps): ReactElement | null {
  if (!authBootstrapped && !needsAuthLogin) {
    return (
      <main className="grid min-h-full place-items-center bg-[#f5f5f5] dark:bg-neutral-950">
        <AuraIconPulse className="text-muted-foreground/50 h-12 w-12" />
      </main>
    )
  }

  if (needsAuthLogin) {
    return (
      <LoginView
        submitting={authLoggingIn || connecting}
        error={authLoginError}
        onRetry={() => {
          setAuthLoginError(null)
          void connect()
        }}
        onSubmit={submitAuthLogin}
        backendUrl={backendUrl}
        onChangeBackend={url => changeBackend(url)}
      />
    )
  }

  if (!health) {
    const backendDown = Boolean(error) && isBackendUnavailableError(error)
    const connectError = error
      ? errorStack
        ? Object.assign(new Error(error), { stack: errorStack })
        : error
      : null

    if (isLocalBackendUrl(backendUrl)) {
      return (
        <AppGatesLocalWaiting
          backendDown={backendDown}
          connecting={connecting}
          connectError={connectError}
          connect={connect}
          backendUrl={backendUrl}
          setBackendUrl={setBackendUrl}
          backendApiKey={backendApiKey}
          setBackendApiKey={setBackendApiKey}
        />
      )
    }

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
          />
          {error ? (
            <ErrorPage
              className="mt-3"
              variant="inline"
              error={
                errorStack
                  ? Object.assign(new Error(error), { stack: errorStack })
                  : error
              }
            />
          ) : null}
        </form>
      </main>
    )
  }

  if (onOnboardingPath) {
    return (
      <div className="h-full min-h-0 overflow-hidden">
        <OnboardingWizardHost
          step={onboardingStep}
          client={client}
          onStepChange={next => {
            const clamped = clampOnboardingStep(next)
            void client
              .updateOnboardingSettings({ step: clamped })
              .catch(() => {})
            navigate(onboardingPath(clamped))
          }}
          onFinish={() => {
            void client
              .updateOnboardingSettings({
                completed: true,
                step: ONBOARDING_MAX_STEP
              })
              .catch(() => {})
            void loadModelOptions()
            void loadIntegrations()
            void loadSkills()
            void loadMcpServers()
            void loadMcpCatalog()
            navigate('/', { replace: true })
          }}
          onExit={() => navigate('/')}
        />
      </div>
    )
  }

  return null
}
