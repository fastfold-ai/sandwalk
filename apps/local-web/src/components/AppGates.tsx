import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { BackendHealth } from '@sandwalk/agent-ui-core'
import type { ReactElement } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { AppGatesLocalWaiting } from '@/components/agents/AppGatesLocalWaiting'
import { AuraIconPulse } from '@/components/agents/AuraIconPulse'
import { LoginView } from '@/components/agents/LoginView'
import { OnboardingWizardHost } from '@/components/agents/OnboardingWizardHost'
import { RemoteBackendConnectForm } from '@/components/agents/RemoteBackendConnectForm'
import { WelcomeHome } from '@/components/agents/WelcomeHome'
import { DesktopGateFrame } from '@/components/DesktopGateFrame'
import { isBackendUnavailableError } from '@/lib/app-error'
import { DEFAULT_BACKEND_URL, isLocalBackendUrl } from '@/lib/backend-url'
import { closeDesktopWindow, isTauri } from '@/lib/desktop'
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
  connectionPaused: boolean
  autoRestoring?: boolean
  setConnectionPaused: (value: boolean) => void
  backendUrl: string
  setBackendUrl: (value: string) => void
  backendApiKey: string
  setBackendApiKey: (value: string) => void
  error: string | null
  errorStack: string | null
  setError: (value: string | null) => void
  onOnboardingPath: boolean
  onboardingStep: number
  client: LocalAgentClient
  navigate: NavigateFunction
  loadModelOptions: () => void | Promise<void>
  loadIntegrations: () => void | Promise<void>
  loadSkills: () => void | Promise<void>
  loadMcpServers: () => void | Promise<void>
  loadMcpCatalog: () => void | Promise<void>
  onOpenRemote: (prefillUrl?: string | null) => void
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
  connectionPaused,
  autoRestoring = false,
  setConnectionPaused,
  backendUrl,
  setBackendUrl,
  backendApiKey,
  setBackendApiKey,
  error,
  errorStack,
  setError,
  onOnboardingPath,
  onboardingStep,
  client,
  navigate,
  loadModelOptions,
  loadIntegrations,
  loadSkills,
  loadMcpServers,
  loadMcpCatalog,
  onOpenRemote
}: AppGatesProps): ReactElement | null {
  if (needsAuthLogin) {
    return (
      <LoginView
        submitting={authLoggingIn || connecting}
        error={authLoginError}
        onRetry={() => {
          setAuthLoginError(null)
          void connect()
        }}
        onSubmit={async (apiKey, remember) => {
          setAuthLoginError(null)
          await submitAuthLogin(apiKey, remember)
        }}
        backendUrl={backendUrl}
        onChangeBackend={url => changeBackend(url)}
      />
    )
  }

  // Desktop cold start — briefly restore last recent before showing Welcome.
  if (connectionPaused && !health && autoRestoring) {
    return (
      <DesktopGateFrame>
        <main className="grid h-full min-h-full place-items-center bg-[#f5f5f5] dark:bg-neutral-950">
          <AuraIconPulse className="text-muted-foreground/50 h-12 w-12" />
        </main>
      </DesktopGateFrame>
    )
  }

  // Desktop cold start / Disconnect — chooser before auto-hitting local.
  if (connectionPaused && !health) {
    return (
      <DesktopGateFrame>
        <WelcomeHome
          connecting={connecting}
          onConnectLocal={() => void changeBackend(DEFAULT_BACKEND_URL)}
          onOpenRemote={onOpenRemote}
        />
      </DesktopGateFrame>
    )
  }

  if (!authBootstrapped && !needsAuthLogin) {
    return (
      <DesktopGateFrame>
        <main className="grid h-full min-h-full place-items-center bg-[#f5f5f5] dark:bg-neutral-950">
          <AuraIconPulse className="text-muted-foreground/50 h-12 w-12" />
        </main>
      </DesktopGateFrame>
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
        <DesktopGateFrame>
          <AppGatesLocalWaiting
            backendDown={backendDown}
            connecting={connecting}
            connectError={connectError}
            connect={connect}
            backendUrl={backendUrl}
            setBackendUrl={setBackendUrl}
            backendApiKey={backendApiKey}
            setBackendApiKey={setBackendApiKey}
            onBackHome={() => {
              setError(null)
              setConnectionPaused(true)
            }}
          />
        </DesktopGateFrame>
      )
    }

    return (
      <DesktopGateFrame>
        <RemoteBackendConnectForm
          backendUrl={backendUrl}
          setBackendUrl={setBackendUrl}
          backendApiKey={backendApiKey}
          setBackendApiKey={setBackendApiKey}
          connecting={connecting}
          connect={connect}
          connectError={connectError}
          dismissLabel="Close"
          onDismiss={() => {
            setError(null)
            if (isTauri()) {
              void closeDesktopWindow().catch(() => {
                setConnectionPaused(true)
              })
              return
            }
            setConnectionPaused(true)
          }}
        />
      </DesktopGateFrame>
    )
  }

  if (onOnboardingPath) {
    return (
      <DesktopGateFrame>
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
      </DesktopGateFrame>
    )
  }

  return null
}
