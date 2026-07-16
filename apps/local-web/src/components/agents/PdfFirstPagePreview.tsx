import { useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

/**
 * Renders only the first PDF page to a canvas — no browser PDF chrome,
 * toolbar, scrollbars, or multi-page scrolling.
 */
export function PdfFirstPagePreview({
  base64,
  url,
  title,
  className,
  /** Extra zoom above fit-width (1 = exact width fit). */
  zoom = 1.15,
  onError
}: {
  base64?: string | null
  url?: string | null
  title?: string
  className?: string
  zoom?: number
  onError?: () => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [failed, setFailed] = useState(false)
  const [ready, setReady] = useState(false)
  const onErrorRef = useRef(onError)
  onErrorRef.current = onError

  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return
    if (!base64 && !url) return

    let cancelled = false
    let resizeObserver: ResizeObserver | null = null
    let pdfDoc: { destroy: () => Promise<void> } | null = null
    setFailed(false)
    setReady(false)

    const run = async () => {
      try {
        const pdfjs = await import('pdfjs-dist')
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          'pdfjs-dist/build/pdf.worker.min.mjs',
          import.meta.url
        ).toString()

        const loadingTask = base64
          ? pdfjs.getDocument({
              data: Uint8Array.from(atob(base64), c => c.charCodeAt(0))
            })
          : pdfjs.getDocument(url!)
        const pdf = await loadingTask.promise
        if (cancelled) {
          await pdf.destroy()
          return
        }
        pdfDoc = pdf
        const page = await pdf.getPage(1)
        if (cancelled) return

        const paint = async () => {
          if (cancelled || !containerRef.current || !canvasRef.current) return
          const width = containerRef.current.clientWidth || 320
          if (width < 8) return

          const base = page.getViewport({ scale: 1 })
          const scale = (width / base.width) * zoom
          const viewport = page.getViewport({ scale })
          const outputScale = Math.min(window.devicePixelRatio || 1, 2)
          const canvasEl = canvasRef.current
          canvasEl.width = Math.floor(viewport.width * outputScale)
          canvasEl.height = Math.floor(viewport.height * outputScale)
          canvasEl.style.width = `${Math.floor(viewport.width)}px`
          canvasEl.style.height = `${Math.floor(viewport.height)}px`

          const context = canvasEl.getContext('2d')
          if (!context) return
          context.setTransform(outputScale, 0, 0, outputScale, 0, 0)
          await page.render({
            canvasContext: context,
            viewport
          }).promise
          if (!cancelled) setReady(true)
        }

        await paint()
        if (cancelled) return
        resizeObserver = new ResizeObserver(() => {
          void paint()
        })
        resizeObserver.observe(container)
      } catch {
        if (!cancelled) {
          setFailed(true)
          onErrorRef.current?.()
        }
      }
    }

    void run()

    return () => {
      cancelled = true
      resizeObserver?.disconnect()
      void pdfDoc?.destroy()
    }
  }, [base64, url, zoom])

  if (failed) {
    return (
      <div
        className={cn(
          'text-muted-foreground grid h-full place-items-center text-sm',
          className
        )}
      >
        PDF preview unavailable
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        'bg-muted/20 relative h-full w-full overflow-hidden',
        className
      )}
      title={title}
    >
      {!ready ? (
        <div className="bg-muted/40 absolute inset-0 animate-pulse" aria-hidden />
      ) : null}
      <canvas
        ref={canvasRef}
        className={cn(
          'block max-w-none transition-opacity',
          ready ? 'opacity-100' : 'opacity-0'
        )}
      />
    </div>
  )
}
