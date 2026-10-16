/** Side by side is horizontal; stacked is vertical. Matches the tiling tree. */
export type PaneSplitDirection = 'horizontal' | 'vertical'

/** What the new pane should be. CLI ids launch that command in a terminal. */
export type PaneSplitTarget =
  | 'agent'
  | 'terminal'
  | 'claude'
  | 'codex'
  | 'opencode'
  | 'fx'
  | 'hermes'
  | 'sandwalk'

export type CliHarnessPreset = {
  id: Exclude<PaneSplitTarget, 'agent' | 'terminal'>
  title: string
  command: string
}

export const CLI_HARNESS_PRESETS: CliHarnessPreset[] = [
  { id: 'claude', title: 'Claude Code', command: 'claude' },
  { id: 'codex', title: 'Codex', command: 'codex' },
  { id: 'opencode', title: 'OpenCode', command: 'opencode' },
  { id: 'fx', title: 'fx', command: 'fx' },
  { id: 'hermes', title: 'Hermes', command: 'hermes' },
  { id: 'sandwalk', title: 'Sandwalk CLI', command: 'sandwalk' }
]

export function cliHarnessPreset(target: PaneSplitTarget): CliHarnessPreset | null {
  return CLI_HARNESS_PRESETS.find(item => item.id === target) ?? null
}
