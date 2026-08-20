/**
 * FAS-107 GF9: activity indicator for terminals.
 *
 * Tracks which terminals have received output while unfocused. Consumers
 * (sidebar row, tab chip) subscribe and render a small orange dot.
 * The PTY WebSocket handler marks activity on message; the terminal
 * clears its own entry when it becomes the active pane.
 *
 * Deliberately dependency-free (no Zustand, no context) — the state is
 * process-scoped and read/written from many independent files.
 */

import { useSyncExternalStore } from 'react'

const activity = new Set<string>()
const listeners = new Set<() => void>()

function emit(): void {
  for (const listener of listeners) listener()
}

export function markTerminalActivity(terminalId: string): void {
  if (activity.has(terminalId)) return
  activity.add(terminalId)
  emit()
}

export function clearTerminalActivity(terminalId: string): void {
  if (!activity.has(terminalId)) return
  activity.delete(terminalId)
  emit()
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

const EMPTY = new Set<string>()

function getSnapshot(): ReadonlySet<string> {
  return activity.size === 0 ? EMPTY : activity
}

/** True when this terminal has unseen output. */
export function useTerminalHasActivity(terminalId: string): boolean {
  const set = useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
  return set.has(terminalId)
}
