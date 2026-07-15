import { ArrowLeft } from 'lucide-react'

import { BusyConfirmOverlay } from '@/components/BusyConfirmOverlay'
import { ErrorPage } from '@/components/ErrorPage'

import { SandboxModalSection } from './sandbox-modal-section'
import { SandboxSettingsSection } from './sandbox-settings-section'
import { useAgentSandboxView } from './use-agent-sandbox-view'

type AgentSandboxViewBodyProps = Parameters<typeof useAgentSandboxView>[0] & {
  onBack?: () => void
  embedded?: boolean
  bare?: boolean
}

export function AgentSandboxViewBody({
  onBack,
  embedded = false,
  bare = false,
  ...sandboxProps
}: AgentSandboxViewBodyProps) {
  const view = useAgentSandboxView(sandboxProps)

  return (
    <>
      <BusyConfirmOverlay
        open={Boolean(view.overlay)}
        phase={view.overlay?.phase || 'working'}
        message={view.overlay?.message || ''}
        description={view.overlay?.description}
      />
      <div
        className={
          bare ? 'space-y-6' : 'mx-auto max-w-3xl space-y-8 px-8 py-10'
        }
      >
        {!bare && onBack ? (
          <div className="flex items-center gap-2 text-sm">
            <button
              type="button"
              onClick={onBack}
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1.5 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </button>
            <span className="text-muted-foreground/40">/</span>
            <button
              type="button"
              onClick={onBack}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              Sandbox
            </button>
          </div>
        ) : null}

        {!bare && !embedded ? (
          <div>
            <h2 className="text-2xl font-semibold">Modal Sandbox</h2>
            <p className="text-muted-foreground mt-2 text-sm">
              Credentials, app defaults, and base images. Compute is chosen per
              chat.
            </p>
          </div>
        ) : null}
        {!bare && embedded ? (
          <div>
            <h2 className="text-lg font-semibold">Modal Sandbox</h2>
          </div>
        ) : null}

        {view.error ? (
          <ErrorPage
            variant="inline"
            className="mt-0"
            error={
              view.errorStack
                ? Object.assign(new Error(view.error), {
                    stack: view.errorStack
                  })
                : view.error
            }
            onRetry={view.onLoadSandboxSettings ? view.retryLoad : undefined}
            retryLabel="Retry load"
          />
        ) : null}

        {view.unavailable && !view.error ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-900 dark:text-amber-200">
            This agent server does not expose{' '}
            <code className="text-xs">/v1/settings/sandbox</code> yet. Restart
            sandwalk / the agent server after updating the CLI, then reload this
            page.
          </div>
        ) : null}

        {!view.unavailable ? (
          <>
            <SandboxModalSection
              modalReady={view.modalReady}
              modalFields={view.modalFields}
              tokenDrafts={view.tokenDrafts}
              formDisabled={view.formDisabled}
              savingTokens={view.savingTokens}
              probeOk={view.probeOk}
              probeDetail={view.probeDetail}
              busy={view.busy}
              overlayMessage={view.overlay?.message ?? null}
              tokenDirty={view.tokenDirty}
              onTokenDraftChange={(envVar, value) => {
                view.setTokenDrafts(current => ({
                  ...current,
                  [envVar]: value
                }))
                view.setProbeOk(false)
                view.setProbeDetail(null)
              }}
              onClearModalTokens={() => void view.clearModalTokens()}
              onRunProbe={() => void view.runProbe()}
              onSaveModalTokens={() => void view.saveModalTokens()}
              canProbe={Boolean(view.onProbeSandbox)}
              canSaveTokens={Boolean(view.onSaveModalIntegration)}
            />

            <SandboxSettingsSection
              draft={view.draft}
              formDisabled={view.formDisabled}
              atDefaults={view.atDefaults}
              dirty={view.dirty}
              busy={view.busy}
              overlayMessage={view.overlay?.message ?? null}
              onDraftChange={view.setDraft}
              onRestoreDefaults={view.restoreDefaults}
              onApply={() => void view.apply()}
            />
          </>
        ) : null}
      </div>
    </>
  )
}
