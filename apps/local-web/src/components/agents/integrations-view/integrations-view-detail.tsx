import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  IntegrationSetupResult,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'
import { CircleCheck, Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import { BusyConfirmOverlay } from '@/components/BusyConfirmOverlay'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

import { IntegrationUnlocksSection } from './integration-unlocks-section'
import {
  IntegrationsDetailHeader,
  IntegrationsDetailNav
} from './integrations-view-detail-header'
import {
  IntegrationsDetailFieldsTable,
  IntegrationsDetailVercelPanel
} from './integrations-view-detail-panels'
import { SlackConnectorPanel } from './slack/SlackConnectorPanel'
import { useIntegrationsDetailView } from './use-integrations-detail-view'
import { VercelAddControls } from './vercel/VercelAddControls'

export function IntegrationsDetailView({
  terminalClient,
  selected,
  values,
  sessions = [],
  onBack,
  onValueChange,
  onSave,
  onValidate,
  onAutofill,
  onSetup,
  onOpenVercelTerminal,
  onRemove
}: {
  terminalClient: LocalAgentClient
  selected: IntegrationSummary
  values: Record<string, string>
  sessions?: AgentSession[]
  onBack: () => void
  onValueChange: (envName: string, value: string) => void
  onSave: (values?: Record<string, string>) => Promise<void>
  onValidate: (key: string) => Promise<{ ok: boolean; message: string }>
  onAutofill: (key: string) => Promise<void>
  onSetup: (key: string) => Promise<IntegrationSetupResult>
  onOpenVercelTerminal: () => Promise<string>
  onRemove: (key: string) => Promise<void>
}) {
  const view = useIntegrationsDetailView({
    selectedKey: selected.key,
    onValidate,
    onAutofill
  })

  const handleLinkProject = () => {
    view.setOpeningTerminal(true)
    view.setAutoFetchPending(false)
    view.autoFetchAttemptsRef.current = 0
    void onOpenVercelTerminal()
      .then(id => {
        view.setTerminalSessionId(id)
        view.setTerminalOpen(true)
        view.setTerminalStartupNonce(current => current + 1)
        view.setSetupRunning(true)
        return onSetup(selected.key)
      })
      .then(result => {
        view.setSetupResult(result)
        toast.success(
          `${result.summary} Use the terminal below to run the listed commands.`
        )
        view.setAutoFetchPending(true)
      })
      .catch(error => {
        view.setSetupResult(null)
        view.setAutoFetchPending(false)
        toast.error(
          error instanceof Error
            ? error.message
            : 'Unable to open Vercel setup.'
        )
      })
      .finally(() => {
        view.setSetupRunning(false)
        view.setOpeningTerminal(false)
      })
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col">
      <BusyConfirmOverlay
        open={Boolean(view.overlay)}
        phase={view.overlay?.phase || 'working'}
        message={view.overlay?.message || ''}
        description={view.overlay?.description}
      />
      <IntegrationsDetailNav selected={selected} onBack={onBack} />
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 pb-6 pt-6 md:px-6 md:pb-8 md:pt-8">
          <IntegrationsDetailHeader selected={selected} />
          <IntegrationUnlocksSection
            client={terminalClient}
            integrationKey={selected.key}
            unlocks={selected.unlocks || []}
          />
          {selected.key === 'slack' ? (
            <SlackConnectorPanel
              client={terminalClient}
              sessions={sessions}
            />
          ) : null}
          {selected.key === 'skills-sh' ? (
            <>
              <VercelAddControls
                busy={
                  view.setupRunning ||
                  view.openingTerminal ||
                  view.validationBusy
                }
                configured={selected.configured}
                setupUrl={selected.setupUrl}
                onRunTerminal={handleLinkProject}
                onSaveToken={async token => {
                  await view.runSaveAndValidate(selected.key, () =>
                    onSave({ VERCEL_OIDC_TOKEN: token })
                  )
                }}
              />
              <IntegrationsDetailVercelPanel
                terminalClient={terminalClient}
                setupResult={view.setupResult}
                terminalOpen={view.terminalOpen}
                terminalSessionId={view.terminalSessionId}
                terminalStartupNonce={view.terminalStartupNonce}
                onCloseTerminal={() => view.setTerminalOpen(false)}
              />
            </>
          ) : null}
          {selected.key !== 'slack' ? (
            <>
              <IntegrationsDetailFieldsTable
                selected={selected}
                values={values}
                onValueChange={onValueChange}
                onRemove={onRemove}
              />
              <div className="flex justify-end gap-2">
                <Button
                  variant="secondary"
                  disabled={view.validationBusy}
                  onClick={() => void view.runValidate(selected.key)}
                >
                  {view.validationBusy ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <CircleCheck className="size-4" />
                  )}
                  Test
                </Button>
                <Button
                  disabled={
                    view.validationBusy ||
                    !Object.values(values).some(value => value.trim())
                  }
                  onClick={() =>
                    void view.runSaveAndValidate(selected.key, onSave)
                  }
                >
                  {view.validationBusy ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : null}
                  Save &amp; Test
                </Button>
              </div>
            </>
          ) : null}
        </div>
      </ScrollArea>
    </div>
  )
}
