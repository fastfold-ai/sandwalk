import { Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

import {
  skillIconForName,
  skillIconInvertInDark
} from '@/lib/skill-icons'
import { cn } from '@/lib/utils'

/** Clickable skill chip matching composer `/` mentions. */
export function SkillMentionChip({
  name,
  className
}: {
  name: string
  className?: string
}) {
  const skillIcon = skillIconForName(name)
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
            skillIconInvertInDark({ name, iconSrc: null }) && 'dark:invert'
          )}
        />
      ) : (
        <Sparkles className="text-primary/80 size-3.5 shrink-0" />
      )}
      <span className="max-w-[200px] truncate">{name}</span>
    </Link>
  )
}
