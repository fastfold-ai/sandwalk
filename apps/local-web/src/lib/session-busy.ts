/** True when POST /messages lost the race with an in-flight run. */
export function isSessionBusyError(message: string) {
  return (
    /\b409\b/.test(message) || /already has an active run/i.test(message)
  )
}
