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

export const PERSONA_CHARACTERS: Array<{
  id: string
  label: string
  archetype: string
  imageUrl: string
  accentColor: string
}> = [
  {
    id: 'capybara',
    label: 'Capybara (O’Reilly Engraving)',
    archetype: 'Calm Polymath',
    imageUrl: '/avatars/capybara.jpg',
    accentColor: '#c9402c'
  },
  {
    id: 'owl',
    label: 'Barn Owl (O’Reilly Engraving)',
    archetype: 'Skeptical Reviewer',
    imageUrl: '/avatars/owl.jpg',
    accentColor: '#0d9488'
  },
  {
    id: 'fox',
    label: 'Red Fox (O’Reilly Engraving)',
    archetype: 'Dreamer & Explorer',
    imageUrl: '/avatars/fox.jpg',
    accentColor: '#d97706'
  },
  {
    id: 'wolf',
    label: 'Timber Wolf (O’Reilly Engraving)',
    archetype: 'Ambitious Generalist',
    imageUrl: '/avatars/wolf.jpg',
    accentColor: '#1d74d8'
  },
  {
    id: 'badger',
    label: 'Badger Builder (O’Reilly Engraving)',
    archetype: 'Project Manager',
    imageUrl: '/avatars/badger.jpg',
    accentColor: '#ea580c'
  },
  {
    id: 'octopus',
    label: 'Pacific Octopus (O’Reilly Engraving)',
    archetype: 'Protein & Systems Architect',
    imageUrl: '/avatars/octopus.jpg',
    accentColor: '#7c3aed'
  },
  {
    id: 'falcon',
    label: 'Peregrine Falcon (O’Reilly Engraving)',
    archetype: 'Fast Computational Scientist',
    imageUrl: '/avatars/falcon.jpg',
    accentColor: '#16a34a'
  },
  {
    id: 'chameleon',
    label: 'Chameleon (O’Reilly Engraving)',
    archetype: 'Omics & Adaptation Analyst',
    imageUrl: '/avatars/chameleon.jpg',
    accentColor: '#4f46e5'
  },
  {
    id: 'capy-field',
    label: 'Meadow Capy (Classic)',
    archetype: 'Field Capybara',
    imageUrl: '/avatars/capy-field.jpg',
    accentColor: '#16a34a'
  }
]

const LEGACY_ANIMAL_ALIASES: Record<string, string> = {
  otium: 'capybara',
  bumble: 'wolf',
  atlas: 'wolf',
  fizz: 'fox',
  nova: 'fox',
  honey: 'badger',
  milo: 'badger',
  soren: 'owl',
  helix: 'octopus',
  orbit: 'falcon',
  spark: 'chameleon'
}

export const SPECIALIST_ICONS: Array<{
  id: SpecialistIcon
  label: string
  Icon: ComponentType<{ className?: string }>
}> = [
  { id: 'capybara' as SpecialistIcon, label: 'Capybara (O’Reilly)', Icon: Bot },
  { id: 'owl' as SpecialistIcon, label: 'Barn Owl (O’Reilly)', Icon: Shield },
  { id: 'fox' as SpecialistIcon, label: 'Red Fox (O’Reilly)', Icon: Sparkles },
  { id: 'wolf' as SpecialistIcon, label: 'Timber Wolf (O’Reilly)', Icon: Bot },
  { id: 'badger' as SpecialistIcon, label: 'Badger (O’Reilly)', Icon: Briefcase },
  { id: 'octopus' as SpecialistIcon, label: 'Octopus (O’Reilly)', Icon: Dna },
  { id: 'falcon' as SpecialistIcon, label: 'Falcon (O’Reilly)', Icon: Zap },
  { id: 'chameleon' as SpecialistIcon, label: 'Chameleon (O’Reilly)', Icon: Microscope },
  { id: 'capy-field' as SpecialistIcon, label: 'Meadow Capy', Icon: Heart },
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

export function resolvePersonaCharacter(
  icon?: string | null,
  _color?: string | null,
  slug?: string | null
) {
  const rawKey = (icon || '').trim().toLowerCase()
  const mappedKey = LEGACY_ANIMAL_ALIASES[rawKey] || rawKey
  const direct = PERSONA_CHARACTERS.find(c => c.id === mappedKey)
  if (direct) return direct

  const slugNorm = (slug || '').toLowerCase()
  if (slugNorm.includes('single-cell')) {
    return PERSONA_CHARACTERS.find(c => c.id === 'octopus')!
  }
  if (slugNorm.includes('genom')) {
    return PERSONA_CHARACTERS.find(c => c.id === 'chameleon')!
  }
  if (slugNorm.includes('target') || slugNorm.includes('molecule')) {
    return PERSONA_CHARACTERS.find(c => c.id === 'falcon')!
  }
  if (slugNorm.includes('protein') || slugNorm.includes('structure')) {
    return PERSONA_CHARACTERS.find(c => c.id === 'octopus')!
  }
  if (slugNorm.includes('dream') || rawKey === 'sparkles') {
    return PERSONA_CHARACTERS.find(c => c.id === 'fox')!
  }
  if (slugNorm.includes('manager') || rawKey === 'briefcase') {
    return PERSONA_CHARACTERS.find(c => c.id === 'badger')!
  }
  if (slugNorm.includes('skeptic') || rawKey === 'shield') {
    return PERSONA_CHARACTERS.find(c => c.id === 'owl')!
  }
  if (slugNorm.includes('generalist')) {
    return PERSONA_CHARACTERS.find(c => c.id === 'wolf')!
  }
  if (rawKey === 'dna' || rawKey === 'atom') {
    return PERSONA_CHARACTERS.find(c => c.id === 'octopus')!
  }
  if (rawKey === 'microscope') {
    return PERSONA_CHARACTERS.find(c => c.id === 'chameleon')!
  }
  if (rawKey === 'flask' || rawKey === 'lightning' || rawKey === 'target') {
    return PERSONA_CHARACTERS.find(c => c.id === 'falcon')!
  }
  if (slugNorm.includes('otium') || slugNorm.includes('relaxed')) {
    return PERSONA_CHARACTERS.find(c => c.id === 'capybara')!
  }
  if (slugNorm) {
    let hash = 0
    for (let i = 0; i < slugNorm.length; i += 1) {
      hash = (hash * 31 + slugNorm.charCodeAt(i)) >>> 0
    }
    const pool = PERSONA_CHARACTERS.slice(1, PERSONA_CHARACTERS.length - 1)
    return pool[hash % pool.length]
  }
  return PERSONA_CHARACTERS[0] // Capybara O'Reilly engraving
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
  avatarUrl,
  slug,
  size = 'sm',
  className
}: {
  color: string | undefined
  icon: string | undefined
  avatarUrl?: string | null
  slug?: string | null
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
}) {
  const sizeClass =
    size === 'xl'
      ? 'size-28'
      : size === 'lg'
        ? 'size-20'
        : size === 'md'
          ? 'size-12'
          : 'size-9'

  const animal = resolvePersonaCharacter(icon, color, slug)
  const src = avatarUrl && avatarUrl.trim() ? avatarUrl.trim() : animal.imageUrl

  return (
    <span
      className={cn(
        'border-border/60 bg-amber-50/60 dark:bg-zinc-900 relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full border shadow-sm',
        sizeClass,
        className
      )}
    >
      <img
        src={src}
        alt={animal.label}
        className="size-full object-cover"
      />
    </span>
  )
}
