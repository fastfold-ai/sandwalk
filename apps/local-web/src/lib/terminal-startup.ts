const PREFIX = 'sandwalk.terminal-startup:'

/** Run once the new terminal's shell is connected. */
export function queueTerminalStartup(terminalId: string, command: string): void {
  try {
    sessionStorage.setItem(PREFIX + terminalId, command)
  } catch {
    // Private mode: the terminal still opens, just without the command.
  }
}

export function takeTerminalStartup(terminalId: string): string | null {
  try {
    const key = PREFIX + terminalId
    const command = sessionStorage.getItem(key)
    if (command) sessionStorage.removeItem(key)
    return command
  } catch {
    return null
  }
}
