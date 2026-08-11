import type { AgentSkill } from '@sandwalk/agent-ui-core'
import { Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import {
  skillIconForName,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

export type SkillIconSkill = Pick<
  AgentSkill,
  'name' | 'iconSrc' | 'author' | 'source'
>

/** Clickable skill chip matching composer `/` mentions. */
export function SkillMentionChip({
  name,
  skills,
  className
}: {
  name: string
  /** Installed skills — used so custom / featured icons match the composer. */
  skills?: SkillIconSkill[]
  className?: string
}) {
  const needle = name.trim().toLowerCase()
  const match = skills?.find(
    skill => skill.name.trim().toLowerCase() === needle
  )
  const skillIcon = skillIconForName(name, skills)
  const invert = skillIconInvertInDark(match || { name, iconSrc: null })
  return (
    <Link
      to={`/dashboard/skills/${encodeURIComponent(name)}`}
      className={cn(
        'border-primary/30 bg-primary/5 text-foreground inline-flex max-w-full items-center gap-1 rounded-full border px-2 py-0.5 align-middle text-xs no-underline hover:underline',
        className
      )}
      title={`Open /${name}`}
    >
      {skillIcon ? (
        <img
          src={skillIcon}
          alt=""
          className={cn(
            'size-3.5 shrink-0 rounded-sm object-contain',
            invert && 'dark:invert'
          )}
        />
      ) : (
        <Sparkles className="text-primary/80 size-3.5 shrink-0" />
      )}
      <span className="max-w-[200px] truncate">{name}</span>
    </Link>
  )
}
