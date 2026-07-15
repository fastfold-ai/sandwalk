import { LocalAgentClient } from '@sandwalk/agent-local-client'
import type {
  IntegrationSetupResult,
  IntegrationSummary
} from '@sandwalk/agent-ui-core'
import { CircleCheck, Loader2 } from 'lucide-react'

import { BusyConfirmOverlay } from '@/components/BusyConfirmOverlay'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

import {
  IntegrationsDetailFieldsTable,
  IntegrationsDetailVercelPanel
} from './integrations-view-detail-panels'
import { IntegrationsDetailHeader } from './integrations-view-detail-header'
import { useIntegrationsDetailView } from './use-integrations-detail-view'

export function IntegrationsDetailView({
  terminalClient,
  selected,
  values,
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
    <ScrollArea className="flex-1">
      <BusyConfirmOverlay
        open={Boolean(view.overlay)}
        phase={view.overlay?.phase || 'working'}
        message={view.overlay?.message || ''}
        description={view.overlay?.description}
      />
      <div className="mx-auto max-w-6xl px-8 py-8">
        <IntegrationsDetailHeader
          selected={selected}
          setupRunning={view.setupRunning}
          openingTerminal={view.openingTerminal}
          onBack={onBack}
          onLinkProject={handleLinkProject}
        />
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
          <p className="text-muted-foreground mt-3 text-sm">
            {view.validationMessage}
          </p>
        ) : null}
        <div className="mt-4 flex justify-end gap-2">
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
  )
}
