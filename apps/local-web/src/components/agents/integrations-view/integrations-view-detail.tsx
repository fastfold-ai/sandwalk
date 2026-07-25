import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  AgentSession,
  IntegrationSetupResult,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'
import { CircleCheck, Loader2 } from 'lucide-react'

import { BusyConfirmOverlay } from '@/components/BusyConfirmOverlay'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

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
  onSave: () => Promise<void>
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
        view.setValidationMessage(
          `${result.summary} Use the terminal below to run the listed commands.`
        )
        view.setAutoFetchPending(true)
      })
      .catch(error => {
        view.setSetupResult(null)
        view.setAutoFetchPending(false)
        view.setValidationMessage(
          error instanceof Error ? error.message : 'Unable to open Vercel setup.'
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
      <IntegrationsDetailNav
        selected={selected}
        setupRunning={view.setupRunning}
        openingTerminal={view.openingTerminal}
        onBack={onBack}
        onLinkProject={handleLinkProject}
      />
      <ScrollArea className="min-h-0 flex-1">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-4 md:p-6">
          <IntegrationsDetailHeader selected={selected} />
          {selected.key === 'slack' ? (
            <>
              <SlackConnectorPanel client={terminalClient} sessions={sessions} />
              <div className="border-border/70 mt-2 border-t pt-4">
                <h3 className="text-[13px] font-medium">Report notifications</h3>
                <p className="text-muted-foreground mt-0.5 text-[12px]">
                  Separate from the connector above — this token is what the
                  agent uses to post reports to a channel.
                </p>
              </div>
            </>
          ) : null}
          {selected.key === 'skills-sh' ? (
            <IntegrationsDetailVercelPanel
              terminalClient={terminalClient}
              setupResult={view.setupResult}
              terminalOpen={view.terminalOpen}
              terminalSessionId={view.terminalSessionId}
              terminalStartupNonce={view.terminalStartupNonce}
              onCloseTerminal={() => view.setTerminalOpen(false)}
            />
          ) : null}
          <IntegrationsDetailFieldsTable
            selected={selected}
            values={values}
            onValueChange={onValueChange}
            onRemove={onRemove}
          />
          {view.validationMessage ? (
            <p className="text-muted-foreground text-sm">
              {view.validationMessage}
            </p>
          ) : null}
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
              Test API Key
            </Button>
            <Button
              disabled={!Object.values(values).some(value => value.trim())}
              onClick={() => void onSave()}
            >
              Save Overrides
            </Button>
          </div>
        </div>
      </ScrollArea>
    </div>
  )
}
