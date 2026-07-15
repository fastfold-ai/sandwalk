import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { useState } from 'react'

type ModelsViewApiKeysInput = {
  load: (discover?: boolean) => Promise<void>
  setError: (error: string | null) => void
  onSaveProviderKey: (
    key: string,
    envVar: string,
    value: string
  ) => Promise<void>
  onClearProviderKey: (key: string) => Promise<void>
}

export function useModelsViewApiKeys({
  load,
  setError,
  onSaveProviderKey,
  onClearProviderKey
}: ModelsViewApiKeysInput) {
  const [apiKeysOpen, setApiKeysOpen] = useState(true)
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({})
  const [savingKeys, setSavingKeys] = useState<Record<string, boolean>>({})
  const [revealedKeys, setRevealedKeys] = useState<Record<string, boolean>>({})

  const saveProviderKey = async (integration: IntegrationSummary) => {
    const envVar =
      integration.fields.find(field => field.isSecret)?.envVar ||
      integration.envVar
    const value = (keyDrafts[integration.key] || '').trim()
    if (!value) {
      setError(`Enter a ${integration.name} API key to save.`)
      return
    }
    setSavingKeys(prev => ({ ...prev, [integration.key]: true }))
    setError(null)
    try {
      await onSaveProviderKey(integration.key, envVar, value)
      setKeyDrafts(prev => ({ ...prev, [integration.key]: '' }))
      await load(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSavingKeys(prev => ({ ...prev, [integration.key]: false }))
    }
  }

  const clearProviderKey = async (integration: IntegrationSummary) => {
    if (
      !window.confirm(
        `Remove the saved ${integration.name} API key from this local agent?`
      )
    ) {
      return
    }
    setSavingKeys(prev => ({ ...prev, [integration.key]: true }))
    setError(null)
    try {
      await onClearProviderKey(integration.key)
      setKeyDrafts(prev => ({ ...prev, [integration.key]: '' }))
      await load(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSavingKeys(prev => ({ ...prev, [integration.key]: false }))
    }
  }

  return {
    apiKeysOpen,
    keyDrafts,
    savingKeys,
    revealedKeys,
    setApiKeysOpen,
    setKeyDrafts,
    setRevealedKeys,
    saveProviderKey,
    clearProviderKey
  }
}
