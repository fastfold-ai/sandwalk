import { Check, ChevronDown, Search } from 'lucide-react'

import {
  SPECIALIST_COLORS,
  SPECIALIST_ICONS,
  SpecialistAvatar
} from '@/components/agents/specialists-view/specialist-ui'
import {
  slugify,
  specialistFieldClassName,
  type SpecialistFormState
} from '@/components/agents/specialists-view/specialists-view-utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

import type { SpecialistsEditorState } from './use-specialists-editor'

export function SpecialistsEditorAppearanceFields({
  state
}: {
  state: SpecialistsEditorState
}) {
  const {
    form,
    setForm,
    slugTouched,
    setSlugTouched,
    appearanceOpen,
    setAppearanceOpen,
    iconQuery,
    setIconQuery
  } = state

  const filteredIcons = SPECIALIST_ICONS.filter(entry => {
    const needle = iconQuery.trim().toLowerCase()
    if (!needle) return true
    return `${entry.label} ${entry.id}`.toLowerCase().includes(needle)
  })

  return (
    <section className="space-y-3">
      <div className="bg-muted/30 flex items-center gap-3 rounded-2xl px-4 py-3.5">
        <DropdownMenu
          open={appearanceOpen}
          onOpenChange={open => {
            setAppearanceOpen(open)
            if (!open) setIconQuery('')
          }}
        >
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="group relative shrink-0 rounded-xl outline-none focus-visible:ring-1 focus-visible:ring-ring"
              aria-label="Choose color and icon"
            >
              <SpecialistAvatar color={form.color} icon={form.icon} />
              <span className="bg-background/90 text-muted-foreground absolute -bottom-1 -right-1 flex size-4 items-center justify-center rounded-full border shadow-sm">
                <ChevronDown className="size-2.5" />
              </span>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="start"
            className="w-64 p-0"
            onCloseAutoFocus={event => event.preventDefault()}
          >
            <div className="space-y-2 p-2">
              <p className="text-muted-foreground px-1 text-[11px] font-medium uppercase tracking-wide">
                Color
              </p>
              <div className="flex flex-wrap gap-1.5 px-1">
                {SPECIALIST_COLORS.map(color => (
                  <button
                    key={color.id}
                    type="button"
                    title={color.label}
                    className={cn(
                      'size-6 rounded-full transition-transform hover:scale-110',
                      color.swatch,
                      form.color === color.id &&
                        'ring-foreground/80 ring-2 ring-offset-2 ring-offset-popover'
                    )}
                    onClick={() =>
                      setForm((current: SpecialistFormState) => ({
                        ...current,
                        color: color.id
                      }))
                    }
                  />
                ))}
              </div>
            </div>
            <div className="border-t px-2 pt-2">
              <p className="text-muted-foreground px-1 pb-1.5 text-[11px] font-medium uppercase tracking-wide">
                Icon
              </p>
              <div className="relative mb-1.5">
                <Search className="text-muted-foreground/70 pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2" />
                <Input
                  value={iconQuery}
                  onChange={event => setIconQuery(event.target.value)}
                  placeholder="Search icons"
                  className="h-8 border-0 bg-transparent pl-7 shadow-none focus-visible:ring-0"
                  autoFocus
                />
              </div>
            </div>
            <div className="chat-scrollbar max-h-56 overflow-y-auto py-1">
              {filteredIcons.length === 0 ? (
                <p className="text-muted-foreground px-3 py-3 text-xs">
                  No icons match.
                </p>
              ) : (
                filteredIcons.map(entry => {
                  const Icon = entry.Icon
                  return (
                    <DropdownMenuItem
                      key={entry.id}
                      className="gap-2"
                      onClick={() =>
                        setForm((current: SpecialistFormState) => ({
                          ...current,
                          icon: entry.id
                        }))
                      }
                    >
                      <Icon className="size-3.5 shrink-0" />
                      <span className="flex-1">{entry.label}</span>
                      {form.icon === entry.id ? (
                        <Check className="text-blue-500 size-3.5" />
                      ) : null}
                    </DropdownMenuItem>
                  )
                })
              )}
            </div>
          </DropdownMenuContent>
        </DropdownMenu>

        <div className="min-w-0 flex-1 space-y-0.5">
          <Input
            value={form.name}
            onChange={event => {
              const name = event.target.value
              setForm((current: SpecialistFormState) => ({
                ...current,
                name,
                slug: slugTouched ? current.slug : slugify(name)
              }))
            }}
            placeholder="Untitled specialist"
            className="placeholder:text-muted-foreground h-7 border-0 bg-transparent px-0 text-sm font-medium shadow-none focus-visible:ring-0"
            autoFocus
          />
          <Input
            value={form.slug}
            onChange={event => {
              setSlugTouched(true)
              setForm((current: SpecialistFormState) => ({
                ...current,
                slug: slugify(event.target.value)
              }))
            }}
            placeholder="slug"
            className="text-muted-foreground placeholder:text-muted-foreground/60 h-5 border-0 bg-transparent px-0 font-mono text-xs shadow-none focus-visible:ring-0"
          />
        </div>
      </div>

      <Input
        value={form.description}
        onChange={event =>
          setForm((current: SpecialistFormState) => ({
            ...current,
            description: event.target.value
          }))
        }
        placeholder="Short description for pickers. Not used by the agent."
        className={specialistFieldClassName()}
      />
      <textarea
        value={form.instructions}
        onChange={event =>
          setForm((current: SpecialistFormState) => ({
            ...current,
            instructions: event.target.value
          }))
        }
        rows={5}
        placeholder="Instructions — appended to the base system prompt. Optional."
        className="border-border/50 bg-muted/40 placeholder:text-muted-foreground focus-visible:ring-ring flex min-h-[8rem] w-full rounded-2xl border-0 px-3.5 py-3 text-sm outline-none focus-visible:ring-1"
      />
    </section>
  )
}
