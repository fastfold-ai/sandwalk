import { type RefObject, useEffect, useState } from 'react'

import { chatScrubberTurns } from '@/lib/chat-scrubber'
import { cn } from '@/lib/utils'

/** Tick width by distance from the hovered tick: a small fisheye. */
const TICK_WIDTHS = ['w-[13px]', 'w-[10px]', 'w-2']

/**
 * A compact stack of tick marks in the chat's left gutter. Each tick is a
 * user turn, in order. The turn being read is dark. Hover widens the tick
 * and its neighbors and shows the prompt with the start of the reply;
 * click jumps to it. Hidden until the chat is long.
 */
export function ChatTranscriptScrubber({
  messages,
  scrollRef,
  onJump
}: {
  messages: { id: string; role: string; content: string }[]
  scrollRef: RefObject<HTMLDivElement | null>
  onJump: (messageId: string) => void
}) {
  const turns = chatScrubberTurns(messages)
  const [hovered, setHovered] = useState<number | null>(null)
  const [current, setCurrent] = useState<string | null>(null)
  const enabled = turns.length >= 2
  const lastTurnId = turns.at(-1)?.id ?? null

  useEffect(() => {
    if (!enabled) return
    const viewport = scrollRef.current?.querySelector<HTMLElement>(
      '[data-radix-scroll-area-viewport]'
    )
    if (!viewport) return
    let frame = 0
    const measure = () => {
      frame = 0
      const atEnd =
        viewport.scrollTop + viewport.clientHeight >= viewport.scrollHeight - 4
      if (atEnd) {
        setCurrent(lastTurnId)
        return
      }
      // The turn being read: the last prompt above the middle of the view.
      const line = viewport.getBoundingClientRect().top + viewport.clientHeight / 2
      let found: string | null = null
      for (const node of viewport.querySelectorAll<HTMLElement>(
        '[data-chat-turn]'
      )) {
        if (node.getBoundingClientRect().top > line) break
        found = node.dataset.chatTurn ?? null
      }
      setCurrent(found)
    }
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure)
    }
    measure()
    viewport.addEventListener('scroll', schedule, { passive: true })
    return () => {
      if (frame) cancelAnimationFrame(frame)
      viewport.removeEventListener('scroll', schedule)
    }
  }, [enabled, lastTurnId, scrollRef, turns.length])

  if (!enabled) return null

  return (
    <div
      className="pointer-events-none absolute inset-y-6 left-3 z-20 flex w-4 flex-col justify-center"
      data-chat-scrubber=""
      onMouseLeave={() => setHovered(null)}
    >
      {turns.map((turn, index) => {
        const distance = hovered == null ? null : Math.abs(hovered - index)
        const near = distance != null && distance < TICK_WIDTHS.length
        return (
          <div
            key={turn.id}
            className="relative flex min-h-0 shrink basis-[9px] items-center"
          >
            <button
              type="button"
              className="pointer-events-auto flex h-full max-h-[9px] min-h-[3px] w-4 items-center"
              aria-label={turn.label}
              onMouseEnter={() => setHovered(index)}
              onFocus={() => setHovered(index)}
              onBlur={() => setHovered(null)}
              onClick={() => onJump(turn.id)}
            >
              <span
                aria-hidden
                className={cn(
                  'h-0.5 rounded-full transition-[width] duration-100',
                  near ? TICK_WIDTHS[distance] : 'w-1.5',
                  turn.id === current
                    ? 'bg-foreground'
                    : near
                      ? 'bg-muted-foreground/80'
                      : 'bg-muted-foreground/35'
                )}
              />
            </button>
            {distance === 0 ? (
              <div className="bg-popover text-popover-foreground pointer-events-none absolute left-9 top-1/2 z-30 w-[17rem] -translate-y-1/2 rounded-lg border px-2.5 py-2 text-left text-xs leading-snug shadow-md">
                <p className="line-clamp-2 font-medium">{turn.label}</p>
                {turn.reply ? (
                  <p className="text-muted-foreground mt-1 line-clamp-3">
                    {turn.reply}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}
