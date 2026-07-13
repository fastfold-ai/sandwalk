import type { AgentMessage } from '@sandwalk/agent-ui-core'

import type { TranscriptTool } from '@/components/agents/ToolCard'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

export function InspectView({
  messages,
  tools,
  onClose
}: {
  messages: AgentMessage[]
  tools: TranscriptTool[]
  onClose: () => void
}) {
  const userTurns = messages.filter(message => message.role === 'user').length
  const assistantTurns = messages.filter(
    message => message.role === 'assistant'
  ).length
  return (
    <ScrollArea className="flex-1">
      <div className="mx-auto max-w-4xl px-8 py-10">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-muted-foreground text-xs uppercase tracking-wide">
              Inspect chat
            </p>
            <h2 className="mt-2 text-3xl font-semibold">
              Session execution overview
            </h2>
          </div>
          <Button variant="outline" onClick={onClose}>
            Back to chat
          </Button>
        </div>
        <div className="mt-8 grid grid-cols-3 gap-3">
          {[
            ['User turns', userTurns],
            ['Assistant turns', assistantTurns],
            ['Tool calls', tools.length]
          ].map(([label, value]) => (
            <div key={label} className="bg-card rounded-xl border p-4">
              <span className="text-muted-foreground text-xs">{label}</span>
              <strong className="mt-2 block text-2xl">{value}</strong>
            </div>
          ))}
        </div>
        <div className="mt-8 space-y-2">
          {tools.map(tool => (
            <div key={tool.id} className="bg-card rounded-lg border p-3">
              <div className="flex items-center justify-between">
                <strong className="text-sm">{tool.name}</strong>
                <span className="text-muted-foreground text-xs capitalize">
                  {tool.status}
                </span>
              </div>
              {tool.result != null ? (
                <pre className="bg-muted/20 mt-3 max-h-52 overflow-auto whitespace-pre-wrap p-3 text-[11px]">
                  {typeof tool.result === 'string'
                    ? tool.result
                    : JSON.stringify(tool.result, null, 2)}
                </pre>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </ScrollArea>
  )
}
