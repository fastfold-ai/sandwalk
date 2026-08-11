import {
  Book,
  Brain,
  Briefcase,
  Code2,
  FlaskConical,
  Folder,
  Globe2,
  Heart,
  type LucideIcon,
  Music,
  Palette,
  Pencil,
  Rocket,
  Sparkles,
  Stethoscope,
  Terminal,
  Wrench
} from 'lucide-react'

export const DEFAULT_PROJECT_ICON = 'folder'
export const DEFAULT_PROJECT_COLOR = 'neutral'

export const PROJECT_COLORS = [
  { id: 'neutral', swatch: 'bg-zinc-400' },
  { id: 'red', swatch: 'bg-red-500' },
  { id: 'orange', swatch: 'bg-orange-500' },
  { id: 'yellow', swatch: 'bg-yellow-400' },
  { id: 'green', swatch: 'bg-emerald-500' },
  { id: 'blue', swatch: 'bg-blue-500' },
  { id: 'purple', swatch: 'bg-violet-500' },
  { id: 'pink', swatch: 'bg-pink-500' }
] as const

export type ProjectColorId = (typeof PROJECT_COLORS)[number]['id']

export const PROJECT_ICONS: Array<{ id: string; Icon: LucideIcon }> = [
  { id: 'folder', Icon: Folder },
  { id: 'book', Icon: Book },
  { id: 'flask', Icon: FlaskConical },
  { id: 'brain', Icon: Brain },
  { id: 'code', Icon: Code2 },
  { id: 'terminal', Icon: Terminal },
  { id: 'briefcase', Icon: Briefcase },
  { id: 'globe', Icon: Globe2 },
  { id: 'heart', Icon: Heart },
  { id: 'music', Icon: Music },
  { id: 'palette', Icon: Palette },
  { id: 'pencil', Icon: Pencil },
  { id: 'rocket', Icon: Rocket },
  { id: 'sparkles', Icon: Sparkles },
  { id: 'stethoscope', Icon: Stethoscope },
  { id: 'wrench', Icon: Wrench }
]

const ICON_MAP = Object.fromEntries(
  PROJECT_ICONS.map(item => [item.id, item.Icon])
) as Record<string, LucideIcon>

const COLOR_TEXT: Record<string, string> = {
  neutral: 'text-zinc-600 dark:text-zinc-300',
  red: 'text-red-600 dark:text-red-400',
  orange: 'text-orange-600 dark:text-orange-400',
  yellow: 'text-yellow-600 dark:text-yellow-400',
  green: 'text-emerald-600 dark:text-emerald-400',
  blue: 'text-blue-600 dark:text-blue-400',
  purple: 'text-violet-600 dark:text-violet-400',
  pink: 'text-pink-600 dark:text-pink-400'
}

const COLOR_BG: Record<string, string> = {
  neutral: 'bg-zinc-500/15',
  red: 'bg-red-500/15',
  orange: 'bg-orange-500/15',
  yellow: 'bg-yellow-500/15',
  green: 'bg-emerald-500/15',
  blue: 'bg-blue-500/15',
  purple: 'bg-violet-500/15',
  pink: 'bg-pink-500/15'
}

export function projectIconComponent(icon: string | null | undefined) {
  return ICON_MAP[icon || DEFAULT_PROJECT_ICON] || Folder
}

export function projectColorTextClass(color: string | null | undefined) {
  return COLOR_TEXT[color || DEFAULT_PROJECT_COLOR] || COLOR_TEXT.neutral
}

export function projectColorBgClass(color: string | null | undefined) {
  return COLOR_BG[color || DEFAULT_PROJECT_COLOR] || COLOR_BG.neutral
}
