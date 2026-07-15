import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import { Check, Loader2 } from 'lucide-react'

import { McpView } from '@/components/agents/McpView'
import { cn } from '@/lib/utils'

import { OnboardingSkillsFeaturedSection } from './onboarding/onboarding-skills-featured-section'
import { OnboardingSkillsSuggestionsSection } from './onboarding/onboarding-skills-suggestions-section'
import { useOnboardingSkills } from './onboarding/use-onboarding-skills'

export function OnboardingSkillsStep({
  client
}: {
  client: LocalAgentClient
}) {
  const skills = useOnboardingSkills(client)

  if (skills.loading && skills.skills.length === 0 && skills.suggestions.length === 0) {
    return (
      <p className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" />
        Loading skills…
      </p>
    )
  }

  return (
    <div className="space-y-5 pb-2">
      <OnboardingSkillsFeaturedSection
        hasFeaturedInstalled={skills.hasFeaturedInstalled}
        featuredInstalled={skills.featuredInstalled}
        pendingEnabled={skills.pendingEnabled}
        installedNames={skills.installedNames}
        selected={skills.selected}
        onSetEnabled={(name, enabled) => void skills.setEnabled(name, enabled)}
        onToggleSelected={name =>
          skills.setSelected(prev => ({
            ...prev,
            [name]: !prev[name]
          }))
        }
      />

      <OnboardingSkillsSuggestionsSection
        suggestions={skills.suggestions}
        installedSuggestionSources={skills.installedSuggestionSources}
        suggestionSelected={skills.suggestionSelected}
        installBusy={skills.installBusy}
        onToggleSuggestion={source =>
          skills.setSuggestionSelected(prev => ({
            ...prev,
            [source]: !prev[source]
          }))
        }
      />

      {(!skills.hasFeaturedInstalled || skills.selectedSuggestions.length > 0) &&
      skills.installCount > 0 ? (
        <div className="flex items-center justify-between gap-3">
          <p className="text-muted-foreground text-xs">
            {skills.installCount} to install
          </p>
          <button
            type="button"
            disabled={skills.installBusy}
            onClick={() => void skills.installSelected()}
            className={cn(
              'bg-foreground text-background inline-flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium transition-opacity',
              skills.installBusy && 'opacity-60'
            )}
          >
            {skills.installBusy ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Check className="size-4" />
            )}
            Install selected
          </button>
        </div>
      ) : null}

      {skills.hasFeaturedInstalled && skills.selectedSuggestions.length === 0 ? (
        <p className="text-muted-foreground text-xs">
          Later you can add more skills in your dashboard.
        </p>
      ) : null}

      {skills.error ? <p className="text-destructive text-sm">{skills.error}</p> : null}
      {skills.notice ? (
        <p className="text-muted-foreground text-sm">{skills.notice}</p>
      ) : null}

      <McpView
        featuredOnly
        featuredLimit={null}
        featuredLabel="MCPs"
        mcpServers={skills.mcpServers}
        catalog={skills.mcpCatalog}
        catalogLoading={skills.mcpLoading}
        onRefresh={skills.refreshMcp}
        onConnectCatalog={async (catalogId, input) => {
          const result = await client.connectMcpCatalog(catalogId, input)
          await skills.refreshMcp()
          return result
        }}
        onToggleCatalog={async (entry, enabled) => {
          await client.setMcpCatalogEnabled(entry.id, enabled)
          await skills.refreshMcp()
        }}
        onCreateMcp={async () => {}}
        onDeleteMcp={async () => {}}
        onToggleCustom={async () => {}}
      />
    </div>
  )
}
