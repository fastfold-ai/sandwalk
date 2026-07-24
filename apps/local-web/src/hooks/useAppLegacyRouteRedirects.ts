import { useEffect } from 'react'
import type { NavigateFunction } from 'react-router-dom'

import { onboardingPath } from '@/lib/onboarding'

type LegacyRouteRedirectArgs = {
  locationPathname: string
  navigate: NavigateFunction
  legacySkillRouteName: string | undefined
  legacyIntegrationRouteKey: string | undefined
  onOnboardingPath: boolean
  onboardingStep: number
}

export function useAppLegacyRouteRedirects({
  locationPathname,
  navigate,
  legacySkillRouteName,
  legacyIntegrationRouteKey,
  onOnboardingPath,
  onboardingStep
}: LegacyRouteRedirectArgs) {
  useEffect(() => {
    if (locationPathname === '/login') {
      navigate('/', { replace: true })
      return
    }
    if (locationPathname === '/agents/home') {
      navigate('/', { replace: true })
      return
    }
    if (locationPathname === '/dashboard/settings') {
      navigate('/dashboard/general', { replace: true })
      return
    }
    if (
      locationPathname.startsWith('/dashboard/status') ||
      locationPathname.startsWith('/dashboard/server') ||
      locationPathname.startsWith('/dashboard/network') ||
      locationPathname.startsWith('/dashboard/advanced') ||
      locationPathname.startsWith('/dashboard/security') ||
      locationPathname.startsWith('/dashboard/logs')
    ) {
      navigate('/dashboard', { replace: true })
      return
    }
    if (locationPathname === '/agents/skills') {
      navigate('/dashboard/skills', { replace: true })
      return
    }
    if (legacySkillRouteName) {
      navigate(`/dashboard/skills/${legacySkillRouteName}`, { replace: true })
      return
    }
    if (locationPathname === '/agents/integrations') {
      navigate('/dashboard/integrations', { replace: true })
      return
    }
    if (legacyIntegrationRouteKey) {
      navigate(
        `/dashboard/integrations/${legacyIntegrationRouteKey}`,
        { replace: true }
      )
      return
    }
    if (onOnboardingPath) {
      const canonical = onboardingPath(onboardingStep)
      if (locationPathname !== canonical) {
        navigate(canonical, { replace: true })
      }
    }
  }, [
    legacyIntegrationRouteKey,
    legacySkillRouteName,
    locationPathname,
    navigate,
    onOnboardingPath,
    onboardingStep
  ])
}
