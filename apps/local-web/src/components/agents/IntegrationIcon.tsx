import type { IntegrationSummary } from '@sandwalk/agent-ui-core'

import { cn } from '@/lib/utils'

export const INTEGRATION_ICONS: Record<
  string,
  { src: string; invertInDark?: boolean }
> = {
  'fastfold-cloud': { src: '/ff_simbol_color.svg' },
  boltz: { src: '/pipelines/boltzgen.svg', invertInDark: true },
  modal: { src: '/modal-logo-icon.png' },
  langsmith: { src: '/langsmith-color.png' },
  nvidia: { src: '/nvidia.svg' },
  opencode: { src: '/opencode.png' },
  openai: { src: '/openai.svg', invertInDark: true },
  anthropic: { src: '/anthropic.png', invertInDark: true },
  xai: { src: '/xai.png' },
  google: { src: '/gemini.png' },
  moonshot: { src: '/kimi.png' },
  deepseek: { src: '/deepseek.svg' },
  minimax: { src: '/minimax.svg' },
  mistral: { src: '/mistral.svg' },
  qwen: { src: '/qwen.svg' },
  together: { src: '/together.svg' },
  openrouter: { src: '/models/openrouter-color.svg' },
  'ibm-rxn': { src: '/ibm.png' },
  lens: { src: '/lens.png' },
  sendgrid: { src: '/sendgrid.png' },
  'lambda-labs': { src: '/lambda.png', invertInDark: true },
  runpod: { src: '/runpod.png' },
  tavily: { src: '/tavily-color.png' },
  slack: { src: '/integrations/slack.png' },
  'skills-sh': { src: '/integrations/vercel.png', invertInDark: true },
  pymol: { src: '/integrations/pymol.png' },
  tamarind: { src: '/integrations/tamarind.png' },
  latch: { src: '/integrations/latch.png' },
  neurosnap: { src: '/integrations/neurosnap.png' },
  paperclip: { src: '/integrations/paperclip.png' },
  huggingface: { src: '/integrations/huggingface.png' },
  linear: { src: '/integrations/linear.png' },
}

export function IntegrationIcon({
  integration,
  size = 'sm'
}: {
  integration: IntegrationSummary
  size?: 'sm' | 'lg'
}) {
  const icon =
    INTEGRATION_ICONS[integration.key] ??
    (integration.key.startsWith('openai') ? INTEGRATION_ICONS.openai : null)
  const imageClass = size === 'lg' ? 'size-9' : 'size-6'
  const fallbackClass = size === 'lg' ? 'size-9' : 'size-6'
  if (icon) {
    return (
      <img
        src={icon.src}
        alt=""
        className={cn(
          imageClass,
          'shrink-0 rounded object-contain',
          icon.invertInDark && 'dark:invert'
        )}
      />
    )
  }
  return (
    <span
      className={cn(
        'bg-muted grid shrink-0 place-items-center rounded text-xs font-semibold',
        fallbackClass
      )}
    >
      {integration.name.slice(0, 2).toUpperCase()}
    </span>
  )
}
