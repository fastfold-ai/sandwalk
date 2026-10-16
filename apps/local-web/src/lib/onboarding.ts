export const ONBOARDING_MAX_STEP = 6

export type OnboardingStepId =
  | 'welcome'
  | 'models'
  | 'agents'
  | 'skills'
  | 'integrations'
  | 'sandbox'
  | 'ready'

/** URL segment under `/onboarding/:slug`. */
export type OnboardingSlug =
  | 'welcome'
  | 'model'
  | 'agents'
  | 'skills'
  | 'integrations'
  | 'sandbox'
  | 'done'

export type OnboardingStepDef = {
  id: OnboardingStepId
  slug: OnboardingSlug
  title: string
  subtitle: string
  skippable: boolean
}

export const ONBOARDING_STEPS: OnboardingStepDef[] = [
  {
    id: 'welcome',
    slug: 'welcome',
    title: 'Make it yours',
    subtitle: 'A walk setup, then you’re in',
    skippable: false
  },
  {
    id: 'models',
    slug: 'model',
    title: 'Model',
    subtitle: 'Add your favorite LLM provider, cloud or local.',
    skippable: true
  },
  {
    id: 'agents',
    slug: 'agents',
    title: 'Your other agents',
    subtitle: 'Bring in sessions from Claude Code, Codex, OpenCode, or fx.',
    skippable: true
  },
  {
    id: 'skills',
    slug: 'skills',
    title: 'Skills & MCPs',
    subtitle: 'Give your agent powerful skills to help you do work',
    skippable: true
  },
  {
    id: 'integrations',
    slug: 'integrations',
    title: 'Integrations & Datasets',
    subtitle: 'Connect tools and install local research data',
    skippable: true
  },
  {
    id: 'sandbox',
    slug: 'sandbox',
    title: 'Sandbox',
    subtitle: 'Local Python environment or Modal cloud compute',
    skippable: true
  },
  {
    id: 'ready',
    slug: 'done',
    title: 'Done',
    subtitle: 'Quick health check, then you’re ready to chat',
    skippable: false
  }
]

/** Older onboarding URLs → current step indices. */
const LEGACY_ONBOARDING_SLUGS: Record<string, number> = {
  keys: 3,
  tools: 3,
  data: 4
}

export function clampOnboardingStep(step: number): number {
  if (!Number.isFinite(step)) return 0
  return Math.max(0, Math.min(ONBOARDING_MAX_STEP, Math.trunc(step)))
}

export function onboardingStepDef(step: number): OnboardingStepDef {
  return ONBOARDING_STEPS[clampOnboardingStep(step)]!
}

export function onboardingPath(step: number | OnboardingSlug): string {
  if (typeof step === 'string') return `/onboarding/${step}`
  return `/onboarding/${onboardingStepDef(step).slug}`
}

export function onboardingStepFromSlug(
  slug: string | null | undefined
): number {
  const needle = String(slug || '')
    .trim()
    .toLowerCase()
  if (!needle) return 0
  const index = ONBOARDING_STEPS.findIndex(item => item.slug === needle)
  if (index >= 0) return index
  if (needle in LEGACY_ONBOARDING_SLUGS) {
    return LEGACY_ONBOARDING_SLUGS[needle]!
  }
  return 0
}

export function isOnboardingPath(pathname: string): boolean {
  return (
    pathname === '/onboarding' || pathname.startsWith('/onboarding/')
  )
}
