import type { IntegrationSetupResult } from '@sandwalk/agent-ui-core'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'

export function useIntegrationsDetailView({
  selectedKey,
  onValidate,
  onAutofill
}: {
  selectedKey: string
  onValidate: (key: string) => Promise<{ ok: boolean; message: string }>
  onAutofill: (key: string) => Promise<void>
}) {
  const [validationBusy, setValidationBusy] = useState(false)
  const [overlay, setOverlay] = useState<{
    phase: 'working' | 'done'
    message: string
    description?: string
  } | null>(null)
  const [setupResult, setSetupResult] = useState<IntegrationSetupResult | null>(
    null
  )
  const [setupRunning, setSetupRunning] = useState(false)
  const [autoFetchPending, setAutoFetchPending] = useState(false)
  const autoFetchAttemptsRef = useRef(0)
  const [terminalSessionId, setTerminalSessionId] = useState<string | null>(null)
  const [terminalOpen, setTerminalOpen] = useState(false)
  const [openingTerminal, setOpeningTerminal] = useState(false)
  const [terminalStartupNonce, setTerminalStartupNonce] = useState(0)

  useEffect(() => {
    setSetupResult(null)
    setAutoFetchPending(false)
    autoFetchAttemptsRef.current = 0
    setValidationBusy(false)
    setOverlay(null)
    setTerminalOpen(false)
  }, [selectedKey])

  async function showDoneOverlay(message: string, description?: string) {
    setOverlay({ phase: 'done', message, description })
    await new Promise(resolve => setTimeout(resolve, 900))
    setOverlay(null)
  }

  async function runValidate(key: string) {
    const isModalProbe = key === 'modal'
    setValidationBusy(true)
    if (isModalProbe) {
      setOverlay({
        phase: 'working',
        message: 'Probing Modal…',
        description:
          'Creating a sandbox, syncing files, and running a health check.'
      })
    }
    try {
      const result = await onValidate(key)
      if (result.ok) toast.success(result.message)
      else toast.error(result.message)
      if (isModalProbe) {
        if (result.ok) {
          await showDoneOverlay(
            'Probe healthy',
            'Modal sandbox is ready to use.'
          )
        } else {
          setOverlay(null)
        }
      }
    } catch (error) {
      setOverlay(null)
      toast.error(
        error instanceof Error
          ? error.message
          : 'Unable to test integration.'
      )
    } finally {
      setValidationBusy(false)
    }
  }

  useEffect(() => {
    if (!autoFetchPending || selectedKey !== 'skills-sh') return
    let cancelled = false
    let timer: number | null = null
    const attemptImport = async () => {
      if (cancelled) return
      try {
        await onAutofill(selectedKey)
        if (cancelled) return
        setAutoFetchPending(false)
        toast.success(
          'Imported Vercel OIDC token into /keys config. Skills.sh search is now enabled.'
        )
      } catch {
        if (cancelled) return
        autoFetchAttemptsRef.current += 1
        if (autoFetchAttemptsRef.current >= 40) {
          setAutoFetchPending(false)
          toast.error(
            'Still waiting for Vercel token. Finish terminal prompts, then click Re-link Project again.'
          )
          return
        }
        timer = window.setTimeout(() => {
          void attemptImport()
        }, 3000)
      }
    }
    timer = window.setTimeout(() => {
      void attemptImport()
    }, 2500)
    return () => {
      cancelled = true
      if (timer !== null) window.clearTimeout(timer)
    }
  }, [autoFetchPending, onAutofill, selectedKey])

  return {
    validationBusy,
    overlay,
    setupResult,
    setupRunning,
    setSetupRunning,
    setSetupResult,
    autoFetchPending,
    setAutoFetchPending,
    autoFetchAttemptsRef,
    terminalSessionId,
    setTerminalSessionId,
    terminalOpen,
    setTerminalOpen,
    openingTerminal,
    setOpeningTerminal,
    terminalStartupNonce,
    setTerminalStartupNonce,
    runValidate
  }
}
