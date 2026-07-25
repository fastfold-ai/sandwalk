import { Plus, Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Popover,
  PopoverContent,
  PopoverTrigger
} from '@/components/ui/popover'
import { cn } from '@/lib/utils'

export type PickerOption = {
  id: string
  label: string
  hint?: string | null
  avatarUrl?: string | null
}

export function initialsOf(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
}

export function Avatar({
  name,
  src,
  className
}: {
  name: string
  src?: string | null
  className?: string
}) {
  if (src) {
    return (
      <img
        src={src}
        alt=""
        className={cn('size-4 shrink-0 rounded-full object-cover', className)}
      />
    )
  }
  return (
    <span
      className={cn(
        'bg-muted-foreground/15 grid size-4 shrink-0 place-items-center rounded-full text-[8px] font-semibold',
        className
      )}
      aria-hidden
    >
      {initialsOf(name)}
    </span>
  )
}

export function SlackPickerPopover({
  label,
  placeholder,
  emptyHint,
  options,
  disabled,
  showAvatars = false,
  onPick
}: {
  label: string
  placeholder: string
  emptyHint: string
  options: PickerOption[]
  disabled?: boolean
  showAvatars?: boolean
  onPick: (option: PickerOption) => void
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase()
    if (!needle) return options.slice(0, 50)
    return options
      .filter(option =>
        `${option.label} ${option.hint ?? ''} ${option.id}`
          .toLowerCase()
          .includes(needle)
      )
      .slice(0, 50)
  }, [options, query])

  const pick = (option: PickerOption) => {
    onPick(option)
    setQuery('')
    setOpen(false)
  }

  return (
    <Popover
      open={open}
      onOpenChange={next => {
        setOpen(next)
        if (!next) setQuery('')
      }}
    >
      <PopoverTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          disabled={disabled}
          className="h-7 gap-1 rounded-full border-dashed px-2.5 text-[12px]"
        >
          <Plus className="size-3" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-0">
        <div className="relative border-b">
          <Search className="text-muted-foreground pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2" />
          <Input
            autoFocus
            value={query}
            placeholder={placeholder}
            onChange={event => setQuery(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && matches.length > 0) {
                pick(matches[0])
              }
            }}
            className="h-9 rounded-none border-0 pl-8 text-[13px] shadow-none focus-visible:ring-0"
          />
        </div>
        <div className="max-h-64 overflow-auto p-1">
          {matches.length === 0 ? (
            <p className="text-muted-foreground px-2 py-6 text-center text-[12px]">
              {options.length === 0 ? emptyHint : 'No matches'}
            </p>
          ) : (
            matches.map(option => (
              <button
                key={option.id}
                type="button"
                onClick={() => pick(option)}
                title={`id ${option.id}`}
                className="hover:bg-muted flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left"
              >
                {showAvatars ? (
                  <Avatar name={option.label} src={option.avatarUrl} />
                ) : null}
                <span className="truncate text-[13px]">{option.label}</span>
                {option.hint ? (
                  <span className="text-muted-foreground truncate text-[12px]">
                    {option.hint}
                  </span>
                ) : null}
              </button>
            ))
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
