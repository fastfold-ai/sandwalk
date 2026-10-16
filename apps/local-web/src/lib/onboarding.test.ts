import { describe, expect, it } from 'vitest'

import {
  clampOnboardingStep,
  isOnboardingPath,
  ONBOARDING_MAX_STEP,
  ONBOARDING_STEPS,
  onboardingPath,
  onboardingStepDef,
  onboardingStepFromSlug
} from './onboarding'

describe('onboarding steps', () => {
  it('defines minimal usable steps', () => {
    expect(ONBOARDING_STEPS).toHaveLength(ONBOARDING_MAX_STEP + 1)
    expect(ONBOARDING_STEPS.map(item => item.id)).toEqual([
      'welcome',
      'models',
      'agents',
      'skills',
      'integrations',
      'sandbox',
      'ready'
    ])
    expect(ONBOARDING_STEPS[0]?.title).toBe('Make it yours')
    expect(ONBOARDING_STEPS[1]?.skippable).toBe(true)
    expect(ONBOARDING_STEPS[2]?.skippable).toBe(true)
    expect(ONBOARDING_STEPS[2]?.slug).toBe('agents')
    expect(ONBOARDING_STEPS[3]?.skippable).toBe(true)
    expect(ONBOARDING_STEPS[4]?.slug).toBe('integrations')
    expect(ONBOARDING_STEPS[5]?.skippable).toBe(true)
    expect(ONBOARDING_STEPS[5]?.slug).toBe('sandbox')
  })

  it('clamps step indices', () => {
    expect(clampOnboardingStep(-2)).toBe(0)
    expect(clampOnboardingStep(99)).toBe(ONBOARDING_MAX_STEP)
    expect(onboardingStepDef(2).title).toBe('Your other agents')
    expect(onboardingStepDef(3).title).toBe('Skills & MCPs')
    expect(onboardingStepDef(4).title).toBe('Integrations & Datasets')
    expect(onboardingStepDef(5).title).toBe('Sandbox')
  })

  it('maps steps to dedicated URLs', () => {
    expect(onboardingPath(0)).toBe('/onboarding/welcome')
    expect(onboardingPath('skills')).toBe('/onboarding/skills')
    expect(onboardingPath(2)).toBe('/onboarding/agents')
    expect(onboardingPath(3)).toBe('/onboarding/skills')
    expect(onboardingPath(4)).toBe('/onboarding/integrations')
    expect(onboardingPath(5)).toBe('/onboarding/sandbox')
    expect(onboardingPath(6)).toBe('/onboarding/done')
    expect(onboardingStepFromSlug('model')).toBe(1)
    expect(onboardingStepFromSlug('agents')).toBe(2)
    // Legacy URLs keep pointing at the step they used to name.
    expect(onboardingStepFromSlug('tools')).toBe(3)
    expect(onboardingStepFromSlug('data')).toBe(4)
    expect(onboardingStepFromSlug('integrations')).toBe(4)
    expect(onboardingStepFromSlug('sandbox')).toBe(5)
    expect(onboardingStepFromSlug('done')).toBe(6)
    expect(onboardingStepFromSlug('unknown')).toBe(0)
    expect(isOnboardingPath('/onboarding')).toBe(true)
    expect(isOnboardingPath('/onboarding/done')).toBe(true)
    expect(isOnboardingPath('/dashboard/general')).toBe(false)
  })
})
