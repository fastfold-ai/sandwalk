import { cn } from '@/lib/utils'

/** Official MCP mark from `/mcp.svg` — inherits text color via mask. */
export function McpMark({ className }: { className?: string }) {
  return (
    <span
      role="img"
      aria-label="MCP"
      className={cn('bg-current inline-block shrink-0', className)}
      style={{
        maskImage: 'url(/mcp.svg)',
        WebkitMaskImage: 'url(/mcp.svg)',
        maskSize: 'contain',
        maskRepeat: 'no-repeat',
        maskPosition: 'center'
      }}
    />
  )
}
