import type { AgentTodo } from '@sandwalk/agent-ui-core'
import { Check, Loader2 } from 'lucide-react'

import { cn } from '@/lib/utils'

export function TodoListInline({
  todos,
  className
}: {
  todos: AgentTodo[]
  className?: string
}) {
  if (todos.length === 0) return null
  return (
    <div
      className={cn(
        'border-border/70 bg-muted/15 space-y-2 rounded-lg border p-3',
        className
      )}
    >
      <div className="flex items-center gap-2">
        <p className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">
          To-dos
        </p>
      </div>
      <div className="space-y-1.5">
        {todos.map(todo => {
          const isCompleted = todo.status === 'completed'
          const isInProgress = todo.status === 'in_progress'
          return (
            <div
              key={`todo-inline-${todo.id}`}
              className="flex items-start gap-2.5 rounded-md px-1 py-1"
            >
              <div className="flex min-w-0 items-start gap-2">
                <span
                  className={cn(
                    'mt-0.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border',
                    isCompleted
                      ? 'border-muted-foreground/60 bg-muted text-muted-foreground'
                      : isInProgress
                      ? 'border-foreground/40 text-foreground'
                      : 'border-muted-foreground/50 text-transparent'
                  )}
                >
                  {isCompleted ? (
                    <Check className="h-3 w-3" />
                  ) : isInProgress ? (
                    <Loader2 className="h-2.5 w-2.5 animate-spin [animation-duration:1.8s]" />
                  ) : null}
                </span>
                <p
                  className={cn(
                    'whitespace-pre-wrap text-[15px] leading-6',
                    isCompleted
                      ? 'text-muted-foreground line-through'
                      : 'text-foreground'
                  )}
                >
                  {todo.activeForm || todo.content}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
