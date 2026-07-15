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

export function buildChatTimelineItems(
  conversationTimeline: TranscriptEntry[]
): ChatTimelineItem[] {
  const items: ChatTimelineItem[] = []
  let cursor = 0
  while (cursor < conversationTimeline.length) {
    const entry = conversationTimeline[cursor]
    if (entry.kind !== 'tool') {
      items.push({
        kind: 'entry',
        key: `${entry.kind}-${cursor}`,
        entry
      })
      cursor += 1
      continue
    }
    const runTools: TranscriptTool[] = []
    while (
      cursor < conversationTimeline.length &&
      conversationTimeline[cursor].kind === 'tool'
    ) {
      const toolEntry = conversationTimeline[cursor]
      if (toolEntry.kind === 'tool') {
        runTools.push(toolEntry.tool)
      }
      cursor += 1
    }
    if (runTools.length > TOOL_RUN_VISIBLE_COUNT) {
      items.push({
        kind: 'tool_run',
        key: `tool-run-${runTools[0]?.id || cursor}`,
        tools: runTools
      })
    } else {
      runTools.forEach((tool, index) => {
        items.push({
          kind: 'entry',
          key: `tool-${tool.id}-${index}`,
          entry: { kind: 'tool', tool }
        })
      })
    }
  }
  return items
}
