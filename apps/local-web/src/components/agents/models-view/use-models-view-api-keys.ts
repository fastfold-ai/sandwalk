import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { useState } from 'react'

export type CloudKeyStatus = 'connected' | 'unreachable' | 'not_set_up'

type ModelsViewApiKeysInput = {
  load: (discover?: boolean) => Promise<void>
  setError: (error: string | null) => void
  onSaveProviderKey: (
    key: string,
    values: Record<string, string>
  ) => Promise<void>
  onClearProviderKey: (key: string) => Promise<void>
  onTestProviderKey: (
    key: string
  ) => Promise<{ ok: boolean; message: string }>
}

/** Auth failures mean the saved secret is bad — drop it so the card is Not set up. */
function isInvalidKeyMessage(message: string) {
  const text = message.toLowerCase()
  return (
    text.includes('invalid api key') ||
    text.includes('authentication failed') ||
    text.includes('unauthorized') ||
    /\bhttp 401\b/.test(text) ||
    /\bhttp 403\b/.test(text)
  )
}

export function useModelsViewApiKeys({
  load,
  setError,
  onSaveProviderKey,
  onClearProviderKey,
  onTestProviderKey
}: ModelsViewApiKeysInput) {
  const [apiKeysOpen, setApiKeysOpen] = useState(true)
  const [keyDrafts, setKeyDrafts] = useState<Record<string, string>>({})
  const [endpointDrafts, setEndpointDrafts] = useState<Record<string, string>>(
    {}
  )
  const [savingKeys, setSavingKeys] = useState<Record<string, boolean>>({})
  const [revealedKeys, setRevealedKeys] = useState<Record<string, boolean>>({})
  /** Overrides card status after Save/Test (Connected vs Unreachable). */
  const [statusByKey, setStatusByKey] = useState<
    Record<string, Exclude<CloudKeyStatus, 'not_set_up'>>
  >({})

  const forgetProviderKey = async (key: string) => {
    await onClearProviderKey(key)
    setKeyDrafts(prev => ({ ...prev, [key]: '' }))
    setRevealedKeys(prev => ({ ...prev, [key]: false }))
    setStatusByKey(prev => {
      const next = { ...prev }
      delete next[key]
      return next
    })
    // Soft refresh so provider model toggles flip off without rediscover flash.
    await load(false)
  }

  const applyProbeResult = async (
    key: string,
    result: { ok: boolean; message: string }
  ) => {
    if (result.ok) {
      setStatusByKey(prev => ({ ...prev, [key]: 'connected' }))
      return result
    }
    // Qwen auth failures are often wrong endpoint/plan — never wipe the key.
    if (key !== 'qwen' && key !== 'bedrock' && isInvalidKeyMessage(result.message)) {
      try {
        await forgetProviderKey(key)
      } catch {
        // Keep the probe error; clear failure is secondary.
      }
      setStatusByKey(prev => {
        const next = { ...prev }
        delete next[key]
        return next
      })
      return result
    }
    // Key may still be present, but the live check failed — match Local.
    setStatusByKey(prev => ({ ...prev, [key]: 'unreachable' }))
    return result
  }

  const saveProviderKey = async (integration: IntegrationSummary) => {
    const envVar =
      integration.fields.find(field => field.isSecret)?.envVar ||
      integration.envVar
    const value = (keyDrafts[integration.key] || '').trim()
    const values: Record<string, string> = {}
    if (value) values[envVar] = value
    if (integration.key === 'qwen') {
      // Empty string clears to Auto-detect on the server.
      values.QWEN_BASE_URL = endpointDrafts[integration.key] ?? ''
    }
    if (integration.key === 'bedrock') {
      values.AWS_REGION =
        endpointDrafts.bedrock_region?.trim() || 'us-east-1'
      values.AWS_PROFILE = endpointDrafts.bedrock_profile ?? ''
      const secret = (endpointDrafts.bedrock_secret || '').trim()
      const token = (endpointDrafts.bedrock_token || '').trim()
      if (value) values.AWS_ACCESS_KEY_ID = value
      if (secret) values.AWS_SECRET_ACCESS_KEY = secret
      if (token) values.AWS_SESSION_TOKEN = token
    }
    if (integration.key !== 'bedrock' && !value && !integration.configured) {
      const message = `Enter a ${integration.name} API key to save.`
      setError(message)
      return { ok: false, message }
    }
    if (!value && Object.keys(values).length === 0) {
      const message = `Enter a ${integration.name} API key to save.`
      setError(message)
      return { ok: false, message }
    }
    setSavingKeys(prev => ({ ...prev, [integration.key]: true }))
    setError(null)
    try {
      await onSaveProviderKey(integration.key, values)
      const result = await onTestProviderKey(integration.key)
      await applyProbeResult(integration.key, result)
      if (result.ok) {
        // Only clear the draft after a successful probe so a failed Test
        // doesn't look like the key vanished.
        if (value) setKeyDrafts(prev => ({ ...prev, [integration.key]: '' }))
        await load(true)
      } else if (!isInvalidKeyMessage(result.message) || integration.key === 'qwen') {
        // Soft refresh so cards/models reflect saved-but-unreachable state.
        await load(false)
      }
      if (!result.ok) setError(result.message)
      return result
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setStatusByKey(prev => ({
        ...prev,
        [integration.key]: 'unreachable'
      }))
      setError(message)
      return { ok: false, message }
    } finally {
      setSavingKeys(prev => ({ ...prev, [integration.key]: false }))
    }
  }

  const clearProviderKey = async (integration: IntegrationSummary) => {
    setSavingKeys(prev => ({ ...prev, [integration.key]: true }))
    setError(null)
    try {
      // Parent reloads integrations (Connected → Not set up). Do not
      // re-discover the models catalog — that makes the whole page flash.
      await forgetProviderKey(integration.key)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      throw err
    } finally {
      setSavingKeys(prev => ({ ...prev, [integration.key]: false }))
    }
  }

  const testProviderKey = async (key: string) => {
    const result = await onTestProviderKey(key)
    await applyProbeResult(key, result)
    if (!result.ok && !isInvalidKeyMessage(result.message)) {
      await load(false)
    } else if (result.ok) {
      await load(false)
    }
    return result
  }

  const cloudStatusFor = (
    integration: IntegrationSummary
  ): CloudKeyStatus => {
    const override = statusByKey[integration.key]
    if (override) return override
    return integration.configured ? 'connected' : 'not_set_up'
  }

  return {
    apiKeysOpen,
    keyDrafts,
    endpointDrafts,
    savingKeys,
    revealedKeys,
    statusByKey,
    setApiKeysOpen,
    setKeyDrafts,
    setEndpointDrafts,
    setRevealedKeys,
    saveProviderKey,
    clearProviderKey,
    testProviderKey,
    cloudStatusFor
  }
}
