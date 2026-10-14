import type { IntegrationSummary } from '@sandwalk/agent-ui-core'
import { Cpu } from 'lucide-react'

import { cn } from '@/lib/utils'

export const LLM_API_KEY_ORDER = [
  'openai',
  'anthropic',
  'google',
  'xai',
  'moonshot',
  'nvidia',
  'opencode',
  'deepseek',
  'minimax',
  'mistral',
  'qwen',
  'together',
  'openrouter',
  'cerebras',
  'groq',
  'fireworks',
  'meta',
  'bedrock'
] as const

/** Same backends as ModelsView local modal / CLI setup. */
export const PROFILE_BACKENDS = [
  {
    value: 'ollama',
    label: 'Ollama',
    hint: '/api/tags',
    baseUrl: 'http://127.0.0.1:11434/v1',
    defaultLabel: 'Ollama',
    icon: '/local-llm/ollama.png'
  },
  {
    value: 'unsloth',
    label: 'Unsloth',
    hint: '/v1/models · auth',
    baseUrl: 'http://127.0.0.1:8888/v1',
    defaultLabel: 'Unsloth',
    icon: '/local-llm/unsloth.png'
  },
  {
    value: 'omlx',
    label: 'oMLX',
    hint: '/v1/models · auth',
    baseUrl: 'http://127.0.0.1:8000/v1',
    defaultLabel: 'oMLX',
    icon: '/local-llm/omlx.png'
  },
  {
    value: 'ds4',
    label: 'DS4',
    hint: '/v1/models',
    baseUrl: 'http://127.0.0.1:8000/v1',
    defaultLabel: 'DS4',
    icon: 'cpu'
  },
  {
    value: 'llama_cpp',
    label: 'llama.cpp',
    hint: '/v1/models',
    baseUrl: 'http://127.0.0.1:8080/v1',
    defaultLabel: 'llama.cpp',
    icon: '/local-llm/llama-cpp.png'
  },
  {
    value: 'lm_studio',
    label: 'LM Studio',
    hint: '/v1/models',
    baseUrl: 'http://127.0.0.1:1234/v1',
    defaultLabel: 'LM Studio',
    icon: '/local-llm/lm-studio.png'
  },
  {
    value: 'other',
    label: 'Other',
    hint: 'OpenAI-compatible',
    baseUrl: 'http://127.0.0.1:11434/v1',
    defaultLabel: 'Custom Compatible Endpoint',
    icon: 'cpu'
  }
] as const

export type OnboardingBackendValue = (typeof PROFILE_BACKENDS)[number]['value']

export function primaryEnvVar(integration: IntegrationSummary) {
  return (
    integration.fields.find(field => field.isSecret)?.envVar ||
    integration.envVar
  )
}

export function primaryMaskedPreview(integration: IntegrationSummary) {
  return (
    integration.fields.find(field => field.isSecret)?.maskedPreview ||
    integration.maskedPreview ||
    null
  )
}

export function OnboardingChip({
  selected,
  onClick,
  children
}: {
  selected: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors',
        selected
          ? 'border-foreground bg-foreground text-background'
          : 'border-border text-muted-foreground hover:text-foreground'
      )}
    >
      {children}
    </button>
  )
}

export function OnboardingBackendIcon({
  icon,
  className
}: {
  icon: string
  className?: string
}) {
  if (icon === 'cpu') {
    return <Cpu className={cn('text-muted-foreground size-4 shrink-0', className)} />
  }
  return (
    <img
      src={icon}
      alt=""
      className={cn('size-4 shrink-0 rounded-sm object-cover', className)}
    />
  )
}
