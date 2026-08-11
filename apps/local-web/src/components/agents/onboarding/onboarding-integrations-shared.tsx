import { cn } from '@/lib/utils'

export function OnboardingConfiguredToggle({
  configured,
  name
}: {
  configured: boolean
  name: string
}) {
  return (
    <span
      role="switch"
      aria-checked={configured}
      aria-label={`${name} ${configured ? 'configured' : 'not configured'}`}
      className={cn(
        'relative inline-flex h-4 w-8 shrink-0 items-center rounded-full transition-colors',
        configured
          ? 'bg-black/75 dark:bg-zinc-300/50'
          : 'bg-zinc-200 dark:bg-zinc-700'
      )}
    >
      <span
        className={cn(
          'inline-block h-3 w-3 rounded-full bg-white shadow-sm transition-transform',
          configured ? 'translate-x-4' : 'translate-x-0.5'
        )}
      />
    </span>
  )
}

export const ONBOARDING_FEATURED_INTEGRATION_ORDER = [
  'skills-sh',
  'boltz',
  'fastfold-cloud',
  'slack'
] as const

export const VERCEL_INTEGRATION_DIR = '~/.sandwalk/vercel-integration'
export const VERCEL_SETUP_RUN_COMMAND =
  'vercel login && vercel link && vercel env pull .env.local --environment=development'
export const VERCEL_SETUP_COMMANDS = [
  `cd "${VERCEL_INTEGRATION_DIR}"`,
  'vercel login',
  'vercel link',
  'vercel env pull .env.local --environment=development'
]
