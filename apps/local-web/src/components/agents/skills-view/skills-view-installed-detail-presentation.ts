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
  const detailVersionLabel = displaySkillVersion(detail.version)
  const detailUpdatedLabel = formatSkillUpdatedLabel(detail.updatedAt)
  const detailGithubUrl = skillGithubUrl(detail.name, detail.source)
  const detailAuthorUrl = skillAuthorUrl(detail.source)

  return {
    detailIconSource,
    detailIconInvert,
    detailVersionLabel,
    detailUpdatedLabel,
    detailGithubUrl,
    detailAuthorUrl
  }
}
