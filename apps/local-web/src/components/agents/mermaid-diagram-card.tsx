import { Check, Code2, Copy, Eye, Maximize2, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import { copyText } from '@/lib/clipboard'
import { cn } from '@/lib/utils'

import {
  MERMAID_CARD_CLASS,
  MERMAID_DIAGRAM_SURFACE_CLASS,
  MERMAID_TAG_CLASS,
  type MermaidRenderResult,
  QUICK_BUTTON_CLASS} from './mermaid-diagram-utils'

function MermaidTitleTag() {
  return (
    <span className={MERMAID_TAG_CLASS}>
      <img
        src="/mermaid-logo.png"
        alt=""
        aria-hidden="true"
        className="h-3.5 w-3.5 rounded-[3px]"
      />
      <span>Mermaid</span>
    </span>
  )
}

function MermaidSourceBlock({
  code,
  withTopBorder = true,
  fullHeight = false
}: {
  code: string
  withTopBorder?: boolean
  fullHeight?: boolean
}) {
  return (
    <div
      className={cn(
        'bg-muted/25',
        withTopBorder && 'border-border/80 border-t',
        fullHeight && 'h-full min-h-0'
      )}
    >
      <pre
        className={cn(
          'overflow-auto px-3 py-2',
          fullHeight ? 'h-full max-h-none min-h-0' : 'max-h-72'
        )}
      >
        <code className="whitespace-pre-wrap font-mono text-xs">
          {code.trim()}
        </code>
      </pre>
    </div>
  )
}

function MermaidSvg({ svg }: { svg: string }) {
  return (
    <div
      className={MERMAID_DIAGRAM_SURFACE_CLASS}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}

export function MermaidCard({
  code,
  className,
  renderResult,
  isLoading
}: {
  code: string
  className?: string
  renderResult: MermaidRenderResult | null
  isLoading: boolean
}) {
  const [showSource, setShowSource] = useState(false)
  const [isFullscreenOpen, setIsFullscreenOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [isMounted, setIsMounted] = useState(false)
  const copyResetTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    setIsMounted(true)
  }, [])

  useEffect(() => {
    return () => {
      if (copyResetTimeoutRef.current) {
        clearTimeout(copyResetTimeoutRef.current)
      }
    }
  }, [])

  useEffect(() => {
    if (!isFullscreenOpen) return
    const onEsc = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsFullscreenOpen(false)
      }
    }
    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onEsc)
    return () => {
      document.body.style.overflow = originalOverflow
      window.removeEventListener('keydown', onEsc)
    }
  }, [isFullscreenOpen])

  const hasRenderableSvg = Boolean(renderResult?.svg && !renderResult.error)
  const sourceToggleLabel = showSource
    ? 'Show rendered Mermaid diagram'
    : 'Show Mermaid source code'
  const sourceToggleTitle = showSource
    ? 'Show rendered diagram'
    : 'Show source'

  const handleCopySource = useCallback(async () => {
    try {
      await copyText(code.trim())
      setCopied(true)
      if (copyResetTimeoutRef.current) {
        clearTimeout(copyResetTimeoutRef.current)
      }
      copyResetTimeoutRef.current = setTimeout(() => {
        setCopied(false)
      }, 1200)
    } catch {
      setCopied(false)
    }
  }, [code])

  const diagramBody = showSource ? (
    <MermaidSourceBlock code={code} withTopBorder={false} />
  ) : (
    <>
      {isLoading ? (
        <div className="bg-muted/35 flex h-[220px] items-center justify-center">
          <div className="border-muted-foreground/25 border-t-muted-foreground/70 h-8 w-8 animate-spin rounded-full border-2" />
        </div>
      ) : hasRenderableSvg ? (
        <MermaidSvg svg={renderResult!.svg!} />
      ) : (
        <div className="bg-muted/20">
          <MermaidSourceBlock code={code} />
          <p className="border-border text-muted-foreground border-t px-3 py-1.5 text-[11px]">
            Diagram could not be rendered, showing raw Mermaid source.
          </p>
        </div>
      )}
    </>
  )

  const fullscreenOverlay =
    isMounted && isFullscreenOpen
      ? createPortal(
          <div className="bg-background/95 fixed inset-0 z-[100] overflow-auto">
            <div className="flex h-full flex-col">
              <div className="border-border flex items-center justify-between border-b px-4 py-3">
                <MermaidTitleTag />
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    className={QUICK_BUTTON_CLASS}
                    onClick={() => void handleCopySource()}
                    title={
                      copied ? 'Copied Mermaid source' : 'Copy Mermaid source'
                    }
                    aria-label={
                      copied ? 'Copied Mermaid source' : 'Copy Mermaid source'
                    }
                  >
                    {copied ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                  </button>
                  <button
                    type="button"
                    className={QUICK_BUTTON_CLASS}
                    onClick={() => setShowSource(current => !current)}
                    title={sourceToggleTitle}
                    aria-label={sourceToggleLabel}
                  >
                    {showSource ? (
                      <Eye className="h-3.5 w-3.5" />
                    ) : (
                      <Code2 className="h-3.5 w-3.5" />
                    )}
                  </button>
                  <button
                    type="button"
                    className={QUICK_BUTTON_CLASS}
                    onClick={() => setIsFullscreenOpen(false)}
                    title="Close full screen"
                    aria-label="Close full screen"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <div className="min-h-0 flex-1 overflow-auto p-4">
                {showSource ? (
                  <MermaidSourceBlock
                    code={code}
                    withTopBorder={false}
                    fullHeight
                  />
                ) : hasRenderableSvg ? (
                  <MermaidSvg svg={renderResult!.svg!} />
                ) : (
                  <MermaidSourceBlock
                    code={code}
                    withTopBorder={false}
                    fullHeight
                  />
                )}
              </div>
            </div>
          </div>,
          document.body
        )
      : null

  return (
    <div className={cn(MERMAID_CARD_CLASS, className)}>
      <div className="border-border/80 flex items-center justify-between gap-2 border-b px-3 py-2">
        <MermaidTitleTag />
        <div className="flex items-center gap-1">
          <button
            type="button"
            className={QUICK_BUTTON_CLASS}
            onClick={() => void handleCopySource()}
            title={copied ? 'Copied Mermaid source' : 'Copy Mermaid source'}
            aria-label={
              copied ? 'Copied Mermaid source' : 'Copy Mermaid source'
            }
          >
            {copied ? (
              <Check className="h-3.5 w-3.5" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
          </button>
          <button
            type="button"
            className={QUICK_BUTTON_CLASS}
            onClick={() => setShowSource(current => !current)}
            title={sourceToggleTitle}
            aria-label={sourceToggleLabel}
          >
            {showSource ? (
              <Eye className="h-3.5 w-3.5" />
            ) : (
              <Code2 className="h-3.5 w-3.5" />
            )}
          </button>
          <button
            type="button"
            className={QUICK_BUTTON_CLASS}
            onClick={() => setIsFullscreenOpen(true)}
            title="Open diagram in full screen"
            aria-label="Open diagram in full screen"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {diagramBody}
      {fullscreenOverlay}
    </div>
  )
}
