import { useEffect, useMemo, useRef, useState } from 'react'

import { cn } from '@/lib/utils'

import { convertParsedToFrameData, parseCIF, parsePDB } from './parsing'
import { initializePy2DmolViewer } from './runtime'

/**
 * Canvas-2D structure thumbnail — same engine/config as FastFold Library cards.
 * Keep controls DOM present for the runtime, but never show it in preview mode.
 */
export function Py2dMolMiniPreview({
  text,
  format,
  viewerId,
  className
}: {
  text: string
  format: 'cif' | 'pdb'
  viewerId: string
  className?: string
}) {
  const rootRef = useRef<HTMLDivElement | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const objectName = useMemo(() => `obj-${viewerId}`, [viewerId])

  useEffect(() => {
    let cancelled = false
    const run = async () => {
      try {
        setError(null)
        setLoading(true)
        const root = rootRef.current
        if (!root) return

        // Match Library thumbnail config exactly.
        const previewConfig = {
          size: [300, 300] as [number, number],
          pae_size: [300, 300] as [number, number],
          color: 'auto' as const,
          shadow: false,
          outline: false,
          width: 3.0,
          rotate: false,
          controls: false,
          autoplay: false,
          box: false,
          pastel: 0.15,
          pae: false,
          colorblind: false,
          viewer_id: viewerId,
          previewMode: true,
          interactive: false
        }
        window.viewerConfig = previewConfig

        initializePy2DmolViewer(root, previewConfig)
        const api = window.py2dmol_viewers?.[viewerId]
        if (!api) throw new Error('Failed to initialize preview')

        // Belt-and-suspenders: runtime updateUIControls can fight Tailwind `hidden`.
        const controls = root.querySelector<HTMLElement>('#controlsContainer')
        if (controls) controls.style.display = 'none'

        if (!text.trim()) throw new Error('Empty structure')
        const isCif =
          format === 'cif' ||
          /^\s*data_/m.test(text) ||
          /_atom_site\./.test(text)
        const models = isCif ? parseCIF(text) : parsePDB(text)
        const model0 = Array.isArray(models) && models.length > 0 ? models[0] : []
        if (!model0 || model0.length === 0) throw new Error('No atoms found')
        if (cancelled) return

        const frame = convertParsedToFrameData(model0)
        if (!frame.coords.length) throw new Error('No backbone atoms')
        api.handlePythonClearAll()
        api.handlePythonNewObject(objectName)
        api.handlePythonUpdate(JSON.stringify(frame), objectName)
        if (controls) controls.style.display = 'none'
      } catch (cause) {
        if (!cancelled) {
          console.error('[py2dmol] preview failed', viewerId, cause)
          setError(cause instanceof Error ? cause.message : 'Failed to render')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void run()
    return () => {
      cancelled = true
      try {
        if (window.py2dmol_viewers?.[viewerId]) {
          delete window.py2dmol_viewers[viewerId]
        }
      } catch {
        // ignore
      }
    }
  }, [format, objectName, text, viewerId])

  return (
    <div
      ref={rootRef}
      className={cn(
        'pointer-events-none relative h-full w-full select-none overflow-hidden',
        className
      )}
      data-viewer-root={viewerId}
    >
      <div id="canvasContainer" className="absolute inset-0 p-2">
        <canvas id="canvas" className="h-full w-full" />
      </div>
      {loading && !error ? (
        <div className="bg-muted/30 absolute inset-0 animate-pulse" />
      ) : null}
      {/* Runtime queries these by id; keep out of a11y/layout (Library pattern). */}
      <div
        id="controlsContainer"
        className="hidden"
        aria-hidden="true"
        style={{ display: 'none' }}
      >
        {/* Use divs — card parent is clickable; nested <button> is invalid HTML. */}
        <div id="playButton" />
        <input id="frameSlider" type="range" tabIndex={-1} />
        <span id="frameCounter" />
        <select id="objectSelect" tabIndex={-1} />
        <select id="speedSelect" tabIndex={-1} />
        <input id="rotationCheckbox" type="checkbox" tabIndex={-1} />
        <input id="lineWidthSlider" type="range" tabIndex={-1} />
        <select id="colorSelect" tabIndex={-1} />
        <input id="shadowEnabledCheckbox" type="checkbox" tabIndex={-1} />
        <input id="outlineEnabledCheckbox" type="checkbox" tabIndex={-1} />
        <input id="colorblindCheckbox" type="checkbox" tabIndex={-1} />
      </div>
      <div id="paeContainer" className="hidden" aria-hidden="true">
        <canvas id="paeCanvas" />
      </div>
      <div id="rightPanelContainer" className="hidden" aria-hidden="true" />
      <div id="objectContainer" className="hidden" aria-hidden="true" />
      {error ? (
        <div className="bg-muted/40 text-muted-foreground absolute inset-0 flex items-center justify-center px-2 text-center text-[10px]">
          {error}
        </div>
      ) : null}
    </div>
  )
}
