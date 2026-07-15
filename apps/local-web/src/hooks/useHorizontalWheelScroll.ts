import { type RefObject, useEffect } from 'react'

/**
 * Translate vertical mouse-wheel / trackpad gestures into horizontal scroll
 * when the container overflows. Native deltaX (horizontal swipe) is left alone.
 */
export function useHorizontalWheelScroll(
  scrollerRef: RefObject<HTMLElement | null>
) {
  useEffect(() => {
    const el = scrollerRef.current
    if (!el) return

    const onWheel = (event: WheelEvent) => {
      if (el.scrollWidth <= el.clientWidth) return
      // Trackpads often send deltaX already — don't fight that.
      if (Math.abs(event.deltaX) > Math.abs(event.deltaY)) return
      if (event.deltaY === 0) return

      const maxScroll = el.scrollWidth - el.clientWidth
      const next = Math.min(
        maxScroll,
        Math.max(0, el.scrollLeft + event.deltaY)
      )
      if (next === el.scrollLeft) return

      event.preventDefault()
      el.scrollLeft = next
    }

    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [scrollerRef])
}
