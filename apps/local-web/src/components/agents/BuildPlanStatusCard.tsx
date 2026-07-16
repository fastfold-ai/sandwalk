import type { AgentPlanCard, AgentTodo } from '@sandwalk/agent-ui-core'
import { Circle, Clock3, ListTree } from 'lucide-react'

import { cn } from '@/lib/utils'

export function BuildPlanStatusCard({
  plan,
  todos,
  runActive,
  className
}: {
  plan: AgentPlanCard
  todos: AgentTodo[]
  runActive: boolean
  className?: string
}) {
  const total = todos.length
  const completed = todos.filter(todo => todo.status === 'completed').length
  const current =
    todos.find(todo => todo.status === 'in_progress') ||
    todos.find(todo => todo.status === 'pending')
  const currentLabel = current?.activeForm || current?.content || ''
  const showProgress = Boolean(currentLabel) && total > 0

  return (
    <div className={cn('space-y-2', className)}>
      <div className="border-border/70 bg-background overflow-hidden rounded-xl border">
        <div className="flex items-center gap-2 px-3.5 py-2.5">
          <span className="text-foreground text-sm font-semibold">Build</span>
          <ListTree className="text-muted-foreground size-3.5 shrink-0" />
          <p className="text-foreground min-w-0 truncate text-sm font-medium">
            {plan.title || plan.path}
          </p>
        </div>
        <div className="border-border/60 flex items-center gap-2 border-t px-3.5 py-2">
          {showProgress ? (
            <>
              <Clock3 className="text-muted-foreground size-3.5 shrink-0" />
              <p className="text-muted-foreground min-w-0 flex-1 truncate text-sm">
                {currentLabel}
              </p>
              <span className="text-muted-foreground shrink-0 text-xs tabular-nums">
                {Math.min(completed + (current?.status === 'in_progress' ? 1 : 0), total)}/
                {total}
              </span>
            </>
          ) : (
            <>
              <Circle className="text-muted-foreground size-3.5 shrink-0" />
              <p className="text-muted-foreground text-sm">
                {total > 0 ? `${total} To-dos` : 'Preparing plan execution'}
              </p>
            </>
          )}
        </div>
      </div>
      {runActive ? (
        <p className="text-muted-foreground px-1 text-sm italic">
          {showProgress ? 'Working through the plan' : 'Planning next moves'}
        </p>
      ) : null}
    </div>
  )
}
