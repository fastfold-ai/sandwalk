import type { AgentSkillDetail } from '@sandwalk/agent-ui-core'

import {
  featuredSkillIcon,
  isFeaturedSkill,
  skillIcon,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import {
  displaySkillVersion,
  formatSkillUpdatedLabel,
  skillAuthorUrl,
  skillGithubUrl
} from '@/lib/skills-catalog'

export function resolveInstalledDetailPresentation(detail: AgentSkillDetail) {
  const detailIconSource = isFeaturedSkill(detail)
    ? featuredSkillIcon(detail)
    : skillIcon(detail)
  const detailIconInvert = skillIconInvertInDark(detail)
  const installed = detail.version
    ? displaySkillVersion(detail.version)
    : detail.commit
      ? detail.commit.slice(0, 7)
      : 'Unknown'
  const rawLatest = String(detail.latestVersion || '').trim()
  const latest = detail.updateAvailable
    ? detail.updateChannel === 'commit' || /^[0-9a-f]{7,40}$/i.test(rawLatest)
      ? rawLatest.slice(0, 7)
      : displaySkillVersion(rawLatest)
    : null
  const detailVersionLabel = installed
  const detailUpdatedLabel = formatSkillUpdatedLabel(detail.updatedAt)
  const detailGithubUrl = skillGithubUrl(detail.name, detail.source)
  const detailAuthorUrl = skillAuthorUrl(detail.source)

  return {
    detailIconSource,
    detailIconInvert,
    detailVersionLabel,
    detailUpdatedLabel,
    detailGithubUrl,
    detailAuthorUrl,
    updateAvailable: Boolean(detail.updateAvailable),
    latestVersionLabel: latest
  }
}
