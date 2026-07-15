import { useEffect, useState } from 'react'

export function useAppChatSkeleton(
  messagesLoaded: boolean,
  runActive: boolean,
  sessionId: string | null
) {
  const [showChatSkeleton, setShowChatSkeleton] = useState(false)

  useEffect(() => {
    if (messagesLoaded || runActive || !sessionId) {
      setShowChatSkeleton(false)
      return
    }
    const timer = window.setTimeout(() => setShowChatSkeleton(true), 180)
    return () => window.clearTimeout(timer)
  }, [messagesLoaded, runActive, sessionId])

  return showChatSkeleton
}
