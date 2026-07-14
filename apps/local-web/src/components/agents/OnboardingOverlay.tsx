import { ArrowLeft, ArrowRight, X } from 'lucide-react'
import type { ReactNode } from 'react'

import './onboarding.css'
import { MirageWalkPath } from '@/components/MirageWalkPath'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  clampOnboardingStep,
  ONBOARDING_MAX_STEP,
  onboardingStepDef
} from '@/lib/onboarding'
import { cn } from '@/lib/utils'

/** Shared shell width so chrome / nav don’t jump between steps. */
const SHELL_CLASS = 'mx-auto flex w-full max-w-3xl flex-col'

/** Dedicated onboarding page shell (not a modal overlay). */
export function OnboardingPage({
  step,
  onStepChange,
  onFinish,
  onExit,
  onSkip,
  canContinue = true,
  continueBusy = false,
  showFinish = true,
  children
}: {
  step: number
  onStepChange: (step: number) => void
  onFinish: () => void
  onExit?: () => void
  /** Skip current optional step without running its side effects. */
  onSkip?: () => void
  canContinue?: boolean
  continueBusy?: boolean
  /** When false, hide Finish on the last step (e.g. while doctor runs). */
  showFinish?: boolean
  children: ReactNode
}) {
  const current = clampOnboardingStep(step)
  const def = onboardingStepDef(current)
  const isFirst = current === 0
  const isLast = current === ONBOARDING_MAX_STEP
  const isWelcome = def.id === 'welcome'
  const isReady = def.id === 'ready'
  const showSkip = def.skippable && !isLast

  return (
    <main className="bg-background flex h-dvh min-h-0 flex-col items-center overflow-hidden px-5 py-6 sm:py-8">
      <div className={cn(SHELL_CLASS, 'h-full min-h-0 max-h-full')}>
        <div className="relative mb-4 flex h-8 shrink-0 items-center justify-between">
          <span className="size-8" aria-hidden />
          {!isReady ? (
            <p className="text-muted-foreground absolute left-1/2 -translate-x-1/2 text-sm tabular-nums">
              {current + 1} / {ONBOARDING_MAX_STEP + 1}
            </p>
          ) : null}
          {onExit ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8"
              onClick={onExit}
              aria-label="Exit setup"
            >
              <X className="size-4" />
            </Button>
          ) : (
            <span className="size-8" />
          )}
        </div>

        <div
          key={def.id}
          className="onboarding-step-body flex min-h-0 flex-1 flex-col overflow-hidden"
        >
          {isWelcome ? (
            <ScrollArea className="min-h-0 flex-1">
              <div className="flex flex-col">
                <div className="mb-3 shrink-0 space-y-1">
                  <h1 className="text-2xl font-semibold tracking-tight">
                    {def.title}
                  </h1>
                  <p className="text-muted-foreground text-sm">{def.subtitle}</p>
                </div>
                <div className="mb-4 shrink-0">{children}</div>
                <div className="flex justify-center pb-2">
                  <MirageWalkPath
                    className="shrink-0"
                    variant="hero"
                    step={current}
                    onStepChange={onStepChange}
                    animateAppear
                  />
                </div>
              </div>
            </ScrollArea>
          ) : isReady ? (
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
              <ScrollArea className="min-h-0 flex-1">
                <div className="flex min-h-[min(60vh,32rem)] items-center justify-center pr-3 pb-1">
                  {children}
                </div>
              </ScrollArea>
            </div>
          ) : (
            <div className="flex min-h-0 flex-1 items-stretch gap-5 overflow-hidden sm:gap-7">
              <MirageWalkPath
                className="hidden shrink-0 self-start sm:flex"
                variant="rail"
                step={current}
                onStepChange={onStepChange}
              />
              <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
                <div className="mb-4 shrink-0 space-y-1">
                  <h1 className="text-2xl font-semibold tracking-tight">
                    {def.title}
                  </h1>
                  <p className="text-muted-foreground text-sm">
                    {def.subtitle}
                  </p>
                </div>
                <ScrollArea className="min-h-0 flex-1">
                  <div className="pr-3 pb-1">{children}</div>
                </ScrollArea>
              </div>
            </div>
          )}
        </div>

        <div className="mt-5 flex h-10 shrink-0 items-center justify-between gap-3">
          <Button
            type="button"
            variant="ghost"
            disabled={isFirst || continueBusy}
            onClick={() => onStepChange(current - 1)}
          >
            <ArrowLeft className="size-4" />
            Back
          </Button>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              className={cn(!showSkip && 'invisible')}
              tabIndex={showSkip ? undefined : -1}
              disabled={!showSkip || continueBusy}
              aria-hidden={!showSkip}
              onClick={() => {
                if (!showSkip) return
                onSkip ? onSkip() : onStepChange(current + 1)
              }}
            >
              Skip
            </Button>
            {isLast ? (
              showFinish ? (
                <Button type="button" onClick={onFinish}>
                  Finish
                  <ArrowRight className="size-4" />
                </Button>
              ) : (
                <span className="inline-flex h-9 w-[5.75rem]" aria-hidden />
              )
            ) : (
              <Button
                type="button"
                disabled={!canContinue || continueBusy}
                onClick={() => onStepChange(current + 1)}
              >
                Continue
                <ArrowRight className="size-4" />
              </Button>
            )}
          </div>
        </div>
      </div>
    </main>
  )
}

/** @deprecated Use OnboardingPage */
export const OnboardingOverlay = OnboardingPage

export function OnboardingChoice({
  title,
  description,
  selected,
  onClick
}: {
  title: string
  description?: string
  selected?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'hover:bg-muted/60 w-full rounded-xl border px-4 py-3 text-left transition-colors',
        selected
          ? 'border-foreground bg-muted/40'
          : 'border-border/70 bg-transparent'
      )}
    >
      <span className="block text-sm font-medium">{title}</span>
      {description ? (
        <span className="text-muted-foreground mt-0.5 block text-xs">
          {description}
        </span>
      ) : null}
    </button>
  )
}
