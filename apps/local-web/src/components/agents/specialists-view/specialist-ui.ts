import type { SpecialistColor, SpecialistIcon } from '@sandwalk/agent-ui-core'
import {
  Atom,
  BarChart3,
  BookOpen,
  Bot,
  Briefcase,
  Code2,
  Database,
  Dna,
  FlaskConical,
  GitBranch,
  Globe,
  Heart,
  MessageSquare,
  Microscope,
  Shield,
  Signpost,
  Sparkles,
  Star,
  Target,
  Zap
} from 'lucide-react'
import type { ComponentType } from 'react'

import { cn } from '@/lib/utils'

export const SPECIALIST_COLORS: Array<{
  id: SpecialistColor
  label: string
  swatch: string
  ink?: boolean
}> = [
  { id: 'ink', label: 'Ink', swatch: 'bg-zinc-900 dark:bg-zinc-100', ink: true },
  { id: 'gray', label: 'Gray', swatch: 'bg-zinc-500' },
  { id: 'red', label: 'Red', swatch: 'bg-red-500' },
  { id: 'orange', label: 'Orange', swatch: 'bg-orange-500' },
  { id: 'amber', label: 'Yellow', swatch: 'bg-amber-400' },
  { id: 'green', label: 'Green', swatch: 'bg-emerald-500' },
  { id: 'teal', label: 'Aqua', swatch: 'bg-teal-500' },
  { id: 'blue', label: 'Blue', swatch: 'bg-blue-500' },
  { id: 'indigo', label: 'Indigo', swatch: 'bg-indigo-500' },
  { id: 'violet', label: 'Violet', swatch: 'bg-violet-500' },
  { id: 'pink', label: 'Magenta', swatch: 'bg-pink-500' }
]

export const SPECIALIST_ICONS: Array<{
  id: SpecialistIcon
  label: string
  Icon: ComponentType<{ className?: string }>
}> = [
  { id: 'agent', label: 'Agent', Icon: Bot },
  { id: 'organization', label: 'Organization', Icon: BarChart3 },
  { id: 'chat', label: 'Chat', Icon: MessageSquare },
  { id: 'lightning', label: 'Lightning', Icon: Zap },
  { id: 'star', label: 'Star', Icon: Star },
  { id: 'signpost', label: 'Signpost', Icon: Signpost },
  { id: 'code', label: 'Command Line', Icon: Code2 },
  { id: 'database', label: 'Database', Icon: Database },
  { id: 'globe', label: 'Globe', Icon: Globe },
  { id: 'flask', label: 'Flask', Icon: FlaskConical },
  { id: 'dna', label: 'DNA', Icon: Dna },
  { id: 'microscope', label: 'Microscope', Icon: Microscope },
  { id: 'book', label: 'Book', Icon: BookOpen },
  { id: 'sparkles', label: 'Sparkles', Icon: Sparkles },
  { id: 'git-branch', label: 'Git Branch', Icon: GitBranch },
  { id: 'target', label: 'Target', Icon: Target },
  { id: 'shield', label: 'Shield', Icon: Shield },
  { id: 'heart', label: 'Heart', Icon: Heart },
  { id: 'briefcase', label: 'Briefcase', Icon: Briefcase },
  { id: 'atom', label: 'Atom', Icon: Atom }
]

export function specialistColorClass(color: string | undefined) {
  return (
    SPECIALIST_COLORS.find(item => item.id === color)?.swatch ??
    SPECIALIST_COLORS[0].swatch
  )
}

function specialistInkOnLight(color: string | undefined) {
  return Boolean(SPECIALIST_COLORS.find(item => item.id === color)?.ink)
}

export function SpecialistGlyph({
  icon,
  className
}: {
  icon: string | undefined
  className?: string
}) {
  const entry =
    SPECIALIST_ICONS.find(item => item.id === icon) ?? SPECIALIST_ICONS[0]
  const Icon = entry.Icon
  return <Icon className={className} />
}

export function SpecialistAvatar({
  color,
  icon,
  className
}: {
  color: string | undefined
  icon: string | undefined
  className?: string
}) {
  const ink = specialistInkOnLight(color)
  return (
    <span
      className={cn(
        'flex size-9 shrink-0 items-center justify-center rounded-xl',
        specialistColorClass(color),
        ink ? 'text-white dark:text-zinc-900' : 'text-white',
        className
      )}
    >
      <SpecialistGlyph icon={icon} className="size-4" />
    </span>
  )
}
