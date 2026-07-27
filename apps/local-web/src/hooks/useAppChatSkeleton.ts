/** Chat skeleton disabled — empty composer stays mounted instead of flashing. */
export function useAppChatSkeleton(
  _messagesLoaded: boolean,
  _runActive: boolean,
  _sessionId: string | null
) {
  return false
}
