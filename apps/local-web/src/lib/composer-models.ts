export type ComposerModelOption = {
  provider: string
  model: string
  label: string
  speed: string
  profileId?: string | null
  source?: 'cloud' | 'profile' | 'custom'
}

export function modelOptionBadge(model: {
  source: string
  provider: string
}): string {
  if (model.source === 'profile' || model.provider === 'local') return 'Local'
  if (model.source === 'custom') return 'Custom'
  if (model.provider === 'anthropic') return 'Anthropic'
  if (model.provider === 'openai') return 'OpenAI'
  if (model.provider === 'google') return 'Gemini'
  if (model.provider === 'xai') return 'Grok'
  if (model.provider === 'nvidia') return 'NVIDIA'
  if (model.provider === 'opencode') return 'OpenCode Zen'
  return model.provider
}

export function toComposerModelOptions(
  models: Array<{
    id: string
    label: string
    provider: string
    source: 'cloud' | 'profile' | 'custom'
    profileId: string | null
    enabled: boolean
  }>
): ComposerModelOption[] {
  return models
    .filter(model => model.enabled)
    .map(model => ({
      provider: model.provider,
      model: model.id,
      label: model.label,
      speed: modelOptionBadge(model),
      profileId: model.profileId,
      source: model.source
    }))
}
