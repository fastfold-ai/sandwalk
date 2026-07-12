import type { ComponentProps } from 'react'
import * as ResizablePrimitive from 'react-resizable-panels'

import { cn } from '@/lib/utils'

const ResizablePanelGroup = ({
  className,
  ...props
}: ComponentProps<typeof ResizablePrimitive.PanelGroup>) => (
  <ResizablePrimitive.PanelGroup
    className={cn(
      'flex h-full w-full data-[panel-group-direction=vertical]:flex-col',
      className
    )}
    {...props}
  />
)

const ResizablePanel = ResizablePrimitive.Panel

const ResizableHandle = ({
  withHandle = true,
  className,
  ...props
}: ComponentProps<typeof ResizablePrimitive.PanelResizeHandle> & {
  withHandle?: boolean
}) => (
  <ResizablePrimitive.PanelResizeHandle
    className={cn(
      'bg-border focus-visible:ring-ring group relative flex w-px items-center justify-center after:absolute after:inset-y-0 after:left-1/2 after:w-1.5 after:-translate-x-1/2 after:content-[""] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-offset-1 data-[panel-group-direction=vertical]:h-px data-[panel-group-direction=vertical]:w-full data-[panel-group-direction=vertical]:after:left-0 data-[panel-group-direction=vertical]:after:h-1.5 data-[panel-group-direction=vertical]:after:w-full data-[panel-group-direction=vertical]:after:translate-x-0 data-[panel-group-direction=vertical]:after:-translate-y-1/2',
      className
    )}
    {...props}
  >
    {withHandle ? (
      <div
        className={cn(
          'bg-muted-foreground/70 z-10 h-6 w-1 rounded-full opacity-0 transition-opacity',
          'group-hover:opacity-100 group-focus-visible:opacity-100 group-active:opacity-100',
          'group-data-[panel-group-direction=vertical]:h-1 group-data-[panel-group-direction=vertical]:w-6'
        )}
      />
    ) : null}
  </ResizablePrimitive.PanelResizeHandle>
)

export { ResizableHandle, ResizablePanel, ResizablePanelGroup }
