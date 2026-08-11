import type { TranscriptTool } from '@/components/agents/ToolCard'
import {
  TOOL_RUN_VISIBLE_COUNT,
  type TranscriptEntry
} from '@/components/agents/transcript'

export type ChatTimelineItem =
  | {
      kind: 'entry'
      key: string
      entry: TranscriptEntry
    }
  | {
      kind: 'tool_run'
      key: string
      tools: TranscriptTool[]
    }

function normalizeToolName(name: string): string {
  return String(name || '')
    .trim()
    .toLowerCase()
    .replace(/_/g, '.')
}

/** Collapse consecutive same-name tools into a single expandable group. */
export function groupConsecutiveSameNameTools(
  tools: TranscriptTool[]
): Array<TranscriptTool | TranscriptTool[]> {
  const groups: Array<TranscriptTool | TranscriptTool[]> = []
  let cursor = 0
  while (cursor < tools.length) {
    const first = tools[cursor]
    const name = normalizeToolName(first.name)
    const batch: TranscriptTool[] = [first]
    cursor += 1
    while (
      cursor < tools.length &&
      normalizeToolName(tools[cursor].name) === name
    ) {
      batch.push(tools[cursor])
      cursor += 1
    }
    if (batch.length > TOOL_RUN_VISIBLE_COUNT) {
      groups.push(batch)
    } else {
      groups.push(batch[0])
    }
  }
  return groups
}

export function buildChatTimelineItems(
  conversationTimeline: TranscriptEntry[]
): ChatTimelineItem[] {
  const items: ChatTimelineItem[] = []
  let cursor = 0
  while (cursor < conversationTimeline.length) {
    const entry = conversationTimeline[cursor]
    if (entry.kind !== 'tool') {
      // Every non-tool kind is covered below, so no positional fallback is
      // needed — TypeScript narrows the last branch to `never`.
      const stableKey =
        entry.kind === 'message' || entry.kind === 'thought'
          ? `${entry.kind}-${entry.message.id}`
          : `${entry.kind}-${entry.messageId}`
      items.push({
        kind: 'entry',
        key: stableKey,
        entry
      })
      cursor += 1
      continue
    }
    const firstTool = entry.tool
    const sameName = normalizeToolName(firstTool.name)
    const runTools: TranscriptTool[] = [firstTool]
    cursor += 1
    while (cursor < conversationTimeline.length) {
      const next = conversationTimeline[cursor]
      if (next.kind !== 'tool') break
      if (normalizeToolName(next.tool.name) !== sameName) break
      runTools.push(next.tool)
      cursor += 1
    }
    if (runTools.length > TOOL_RUN_VISIBLE_COUNT) {
      const runKey = runTools.map(tool => tool.id).join('-')
      items.push({
        kind: 'tool_run',
        key: `tool-run-${runKey || cursor}`,
        tools: runTools
      })
    } else {
      for (const tool of runTools) {
        items.push({
          kind: 'entry',
          key: `tool-${tool.id}`,
          entry: { kind: 'tool', tool }
        })
      }
    }
  }
  return items
}
