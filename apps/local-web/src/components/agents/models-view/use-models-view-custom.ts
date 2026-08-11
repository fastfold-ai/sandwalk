import type { AgentModel, CreateAgentModelInput } from '@sandwalk/agent-ui-core'
import { useState } from 'react'

type ModelsViewCustomInput = {
  load: (discover?: boolean) => Promise<void>
  setError: (error: string | null) => void
  onCreateCustomModel: (
    input: CreateAgentModelInput,
    signal?: AbortSignal
  ) => Promise<AgentModel>
  onDeleteCustomModel: (
    modelId: string,
    signal?: AbortSignal
  ) => Promise<void>
}

export function useModelsViewCustom({
  load,
  setError,
  onCreateCustomModel,
  onDeleteCustomModel
}: ModelsViewCustomInput) {
  const [customOpen, setCustomOpen] = useState(true)
  const [customDialogOpen, setCustomDialogOpen] = useState(false)
  const [savingCustom, setSavingCustom] = useState(false)
  const [customForm, setCustomForm] = useState({
    provider: 'openai',
    id: '',
    label: ''
  })

  const openCustomCreate = () => {
    setCustomForm({ provider: 'openai', id: '', label: '' })
    setCustomDialogOpen(true)
  }

  const saveCustomModel = async () => {
    const modelId = customForm.id.trim()
    if (!modelId) {
      setError('Enter a cloud model name (for example gpt-4.1-mini).')
      return
    }
    setSavingCustom(true)
    setError(null)
    try {
      await onCreateCustomModel({
        id: modelId,
        provider: customForm.provider,
        label: customForm.label.trim() || modelId
      })
      setCustomDialogOpen(false)
      await load(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSavingCustom(false)
    }
  }

  const removeCustomModel = async (model: AgentModel) => {
    if (!window.confirm(`Remove custom model “${model.label}” from the list?`)) {
      return
    }
    setError(null)
    try {
      await onDeleteCustomModel(model.id)
      await load(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return {
    customOpen,
    customDialogOpen,
    savingCustom,
    customForm,
    setCustomOpen,
    setCustomDialogOpen,
    setCustomForm,
    openCustomCreate,
    saveCustomModel,
    removeCustomModel
  }
}
