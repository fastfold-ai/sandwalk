import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import {
  Check,
  ChevronDown,
  ChevronRight,
  Eye,
  EyeOff,
  Loader2,
  Trash2
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { IntegrationIcon } from '@/components/agents/IntegrationIcon'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { openInSystemBrowser } from '@/lib/desktop'
import { cn } from '@/lib/utils'

import type { CloudKeyStatus } from './use-models-view-api-keys'
import {
  LLM_API_KEY_COPY,
  LLM_API_KEY_ORDER,
  primaryMaskedPreview
} from './models-view-utils'

function providerCopy(key: string) {
  return LLM_API_KEY_COPY[key as (typeof LLM_API_KEY_ORDER)[number]]
}

function setupHostLabel(url: string, fallback?: string) {
  if (fallback) return fallback
  try {
    return new URL(url).hostname
  } catch {
    return 'provider site'
  }
}

function cloudStatusLabel(status: CloudKeyStatus) {
  if (status === 'connected') {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
        <Check className="size-3.5 shrink-0" />
        Connected
      </span>
    )
  }
  if (status === 'unreachable') {
    return (
      <span className="text-xs font-medium text-amber-700 dark:text-amber-400">
        Unreachable
      </span>
    )
  }
  return (
    <span className="text-muted-foreground block text-xs">Not set up</span>
  )
}

export function ModelsApiKeysSection({
  open,
  providerIntegrations,
  keyDrafts,
  savingKeys,
  revealedKeys,
  cloudStatusFor,
  onOpenChange,
  onKeyDraftChange,
  onRevealedKeyChange,
  onSaveProviderKey,
  onClearProviderKey,
  onTestProviderKey
}: {
  open: boolean
  providerIntegrations: IntegrationSummary[]
  keyDrafts: Record<string, string>
  savingKeys: Record<string, boolean>
  revealedKeys: Record<string, boolean>
  cloudStatusFor: (integration: IntegrationSummary) => CloudKeyStatus
  onOpenChange: (open: boolean) => void
  onKeyDraftChange: (key: string, value: string) => void
  onRevealedKeyChange: (key: string, revealed: boolean) => void
  onSaveProviderKey: (
    integration: IntegrationSummary
  ) => Promise<{ ok: boolean; message: string } | void> | void
  onClearProviderKey: (integration: IntegrationSummary) => Promise<void> | void
  onTestProviderKey: (
    key: string
  ) => Promise<{ ok: boolean; message: string }>
}) {
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{
    ok: boolean
    message: string
  } | null>(null)

  const activeIntegration = useMemo(
    () =>
      providerIntegrations.find(item => item.key === activeKey) || null,
    [activeKey, providerIntegrations]
  )

  useEffect(() => {
    setTestResult(null)
    setTesting(false)
  }, [activeKey])

  const activeCopy = activeIntegration
    ? providerCopy(activeIntegration.key)
    : null
  const activeDraft = activeIntegration
    ? keyDrafts[activeIntegration.key] || ''
    : ''
  const activeSaving = activeIntegration
    ? Boolean(savingKeys[activeIntegration.key])
    : false
  const canTest = Boolean(
    activeIntegration &&
      (activeIntegration.configured || activeDraft.trim())
  )

  const runTest = async () => {
    if (!activeIntegration) return
    setTesting(true)
    setTestResult(null)
    try {
      if (typeof onTestProviderKey !== 'function') {
        setTestResult({
          ok: false,
          message: 'Test is unavailable. Reload the Models page and try again.'
        })
        return
      }
      // Draft present → Save already runs a live probe; reuse that path.
      if (activeDraft.trim()) {
        const result = await onSaveProviderKey(activeIntegration)
        if (result) setTestResult(result)
        return
      }
      const result = await onTestProviderKey(activeIntegration.key)
      setTestResult(result)
    } catch (err) {
      setTestResult({
        ok: false,
        message:
          err instanceof Error ? err.message : 'Unable to test API key.'
      })
    } finally {
      setTesting(false)
    }
  }

  const runSave = async () => {
    if (!activeIntegration) return
    setTesting(true)
    setTestResult(null)
    try {
      const result = await onSaveProviderKey(activeIntegration)
      if (result) setTestResult(result)
    } catch (err) {
      setTestResult({
        ok: false,
        message:
          err instanceof Error ? err.message : 'Unable to save API key.'
      })
    } finally {
      setTesting(false)
    }
  }

  const runClear = async () => {
    if (!activeIntegration) return
    setTestResult(null)
    try {
      await onClearProviderKey(activeIntegration)
      setActiveKey(null)
    } catch (err) {
      setTestResult({
        ok: false,
        message:
          err instanceof Error ? err.message : 'Unable to remove API key.'
      })
    }
  }

  return (
    <section className="space-y-4">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => onOpenChange(!open)}
      >
        <div className="min-w-0 pr-3">
          <h3 className="text-base font-semibold">Cloud</h3>
          <p className="text-muted-foreground mt-1 text-sm">
            Providers and the models offered in the composer picker. Keys are
            stored only on this computer.
          </p>
        </div>
        <ChevronDown
          className={cn(
            'text-muted-foreground size-4 shrink-0 transition-transform',
            open && 'rotate-180'
          )}
        />
      </button>

      {open ? (
        <div className="space-y-3">
          {providerIntegrations.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No LLM provider integrations available from the agent backend.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {providerIntegrations.map(integration => {
                const copy = providerCopy(integration.key)
                const title =
                  copy?.cardTitle || integration.name || integration.key
                return (
                  <button
                    key={integration.key}
                    type="button"
                    onClick={() => setActiveKey(integration.key)}
                    className="hover:bg-muted/40 flex h-16 items-center gap-3 rounded-xl border px-3 text-left transition-colors"
                  >
                    <span className="bg-muted/50 grid size-9 shrink-0 place-items-center rounded-lg">
                      <IntegrationIcon integration={integration} size="sm" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">
                        {title}
                      </span>
                      {cloudStatusLabel(cloudStatusFor(integration))}
                    </span>
                    <ChevronRight className="text-muted-foreground size-4 shrink-0" />
                  </button>
                )
              })}
            </div>
          )}
        </div>
      ) : null}

      <Dialog
        open={Boolean(activeIntegration)}
        onOpenChange={next => {
          if (!next) setActiveKey(null)
        }}
      >
        <DialogContent className="max-w-lg">
          {activeIntegration ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-3">
                  <span className="bg-muted/50 grid size-9 place-items-center rounded-lg">
                    <IntegrationIcon
                      integration={activeIntegration}
                      size="sm"
                    />
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate">
                      {activeCopy?.title ||
                        `${activeIntegration.name} API Key`}
                    </span>
                    <span className="text-muted-foreground text-xs font-normal">
                      {cloudStatusFor(activeIntegration) === 'connected'
                        ? 'Secret saved'
                        : cloudStatusFor(activeIntegration) === 'unreachable'
                          ? 'Key saved · unreachable'
                          : 'Not set'}
                    </span>
                  </span>
                </DialogTitle>
              </DialogHeader>

              <div className="space-y-4">
                <p className="text-muted-foreground text-sm leading-relaxed">
                  {activeCopy?.description || activeIntegration.description}
                </p>

                <div className="relative">
                  <Input
                    type={
                      revealedKeys[activeIntegration.key] ? 'text' : 'password'
                    }
                    value={activeDraft}
                    autoComplete="off"
                    autoFocus
                    onChange={event =>
                      onKeyDraftChange(
                        activeIntegration.key,
                        event.target.value
                      )
                    }
                    placeholder={
                      activeIntegration.configured
                        ? primaryMaskedPreview(activeIntegration) ||
                          'Secret saved. Enter a new key to replace it.'
                        : activeCopy?.placeholderUnset ||
                          `Enter your ${activeIntegration.name} API Key`
                    }
                    className="bg-muted/40 pr-9 font-mono text-sm"
                    onKeyDown={event => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        void runSave()
                      }
                    }}
                  />
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground absolute right-2 top-1/2 -translate-y-1/2"
                    aria-label={
                      revealedKeys[activeIntegration.key]
                        ? 'Hide API key'
                        : 'Show API key'
                    }
                    onClick={() =>
                      onRevealedKeyChange(
                        activeIntegration.key,
                        !revealedKeys[activeIntegration.key]
                      )
                    }
                  >
                    {revealedKeys[activeIntegration.key] ? (
                      <EyeOff className="size-4" />
                    ) : (
                      <Eye className="size-4" />
                    )}
                  </button>
                </div>

                {activeIntegration.setupUrl ? (
                  <p className="text-muted-foreground text-sm">
                    No key yet?{' '}
                    <button
                      type="button"
                      className="text-foreground underline underline-offset-2"
                      onClick={() =>
                        void openInSystemBrowser(activeIntegration.setupUrl!)
                      }
                    >
                      Create one at{' '}
                      {setupHostLabel(
                        activeIntegration.setupUrl,
                        activeCopy?.hostLabel
                      )}{' '}
                      ↗
                    </button>
                  </p>
                ) : null}

                {testResult ? (
                  <p
                    className={cn(
                      'rounded-md px-3 py-2 text-sm',
                      testResult.ok
                        ? 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                        : 'bg-amber-500/15 text-amber-900 dark:text-amber-200'
                    )}
                  >
                    {testResult.message}
                  </p>
                ) : null}
              </div>

              <DialogFooter className="gap-2 sm:justify-between">
                <div className="flex flex-wrap gap-2">
                  {activeIntegration.configured ? (
                    <Button
                      variant="ghost"
                      className="text-destructive hover:text-destructive"
                      disabled={activeSaving || testing}
                      onClick={() => void runClear()}
                    >
                      {activeSaving ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <Trash2 />
                      )}
                      Remove
                    </Button>
                  ) : null}
                  <Button
                    variant="ghost"
                    disabled={!canTest || activeSaving || testing}
                    onClick={() => void runTest()}
                  >
                    {testing ? <Loader2 className="animate-spin" /> : null}
                    Test
                  </Button>
                </div>
                <div className="flex flex-wrap justify-end gap-2">
                  <Button variant="ghost" onClick={() => setActiveKey(null)}>
                    Cancel
                  </Button>
                  <Button
                    disabled={activeSaving || testing || !activeDraft.trim()}
                    onClick={() => void runSave()}
                  >
                    {activeSaving || testing ? (
                      <Loader2 className="animate-spin" />
                    ) : null}
                    Save
                  </Button>
                </div>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </section>
  )
}
