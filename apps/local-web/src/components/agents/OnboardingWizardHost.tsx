import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { useEffect, useState, type ReactNode } from 'react'

import { OnboardingDoneStep } from '@/components/agents/OnboardingDoneStep'
import { OnboardingIntegrationsStep } from '@/components/agents/OnboardingIntegrationsStep'
import { OnboardingModelStep } from '@/components/agents/OnboardingModelStep'
import { OnboardingPage } from '@/components/agents/OnboardingOverlay'
import { OnboardingSandboxStep } from '@/components/agents/OnboardingSandboxStep'
import { OnboardingSkillsStep } from '@/components/agents/OnboardingSkillsStep'
import {
  clampOnboardingStep,
  onboardingStepDef
} from '@/lib/onboarding'

export function OnboardingWizardHost({
  step,
  client,
  onStepChange,
  onFinish,
  onExit
}: {
  step: number
  client: LocalAgentClient
  onStepChange: (step: number) => void
  onFinish: () => void
  onExit?: () => void
}) {
  const current = clampOnboardingStep(step)
  const def = onboardingStepDef(current)

  const [error, setError] = useState<string | null>(null)
  const [doneLoading, setDoneLoading] = useState(() => def.id === 'ready')

  useEffect(() => {
    setError(null)
    setDoneLoading(def.id === 'ready')
  }, [current, def.id])

  let body: ReactNode = null

  if (def.id === 'welcome') {
    body = (
      <p className="text-muted-foreground text-[15px] leading-relaxed">
        This is your bench for hard problems, with tools crafted for science,
        and room to make them your own.
      </p>
    )
  } else if (def.id === 'models') {
    body = <OnboardingModelStep client={client} />
  } else if (def.id === 'skills') {
    body = <OnboardingSkillsStep client={client} />
  } else if (def.id === 'integrations') {
    body = <OnboardingIntegrationsStep client={client} />
  } else if (def.id === 'sandbox') {
    body = <OnboardingSandboxStep client={client} />
  } else if (def.id === 'ready') {
    body = (
      <OnboardingDoneStep client={client} onLoadingChange={setDoneLoading} />
    )
  } else {
    body = null
  }

  return (
    <OnboardingPage
      step={current}
      onStepChange={onStepChange}
      onSkip={() => onStepChange(clampOnboardingStep(current + 1))}
      onFinish={onFinish}
      onExit={onExit}
      showFinish={!doneLoading}
    >
      <div className="flex min-h-0 flex-col gap-3">
        {body}
        {error ? (
          <p className="text-destructive text-sm">{error}</p>
        ) : null}
      </div>
    </OnboardingPage>
  )
}
