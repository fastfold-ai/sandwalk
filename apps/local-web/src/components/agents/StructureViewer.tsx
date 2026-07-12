import 'molstar/build/viewer/molstar.css'

import { useEffect, useRef, useState } from 'react'

const DARK_BG = 0x08080a
const LIGHT_BG = 0xffffff

function isDocumentDark() {
  return (
    typeof document !== 'undefined' &&
    document.documentElement.classList.contains('dark')
  )
}

export function StructureViewer({
  data,
  format,
  compact = false
}: {
  data: string
  format: 'pdb' | 'cif' | 'sdf'
  /** Lightweight thumbnail mode — no chrome, smaller footprint. */
  compact?: boolean
}) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dark, setDark] = useState(isDocumentDark)

  useEffect(() => {
    const sync = () => setDark(isDocumentDark())
    sync()
    const observer = new MutationObserver(sync)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class']
    })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!hostRef.current) return
    let active = true
    let viewer: import('molstar/lib/apps/viewer/app').Viewer | null = null
    const host = hostRef.current
    host.innerHTML = ''

    void import('molstar/lib/apps/viewer/app')
      .then(async ({ Viewer }) => {
        if (!active) return
        viewer = await Viewer.create(host, {
          layoutIsExpanded: false,
          layoutShowControls: false,
          layoutShowRemoteState: false,
          layoutShowSequence: false,
          layoutShowLog: false,
          layoutShowLeftPanel: false,
          collapseRightPanel: true,
          viewportShowControls: !compact,
          viewportShowExpand: false,
          viewportShowSettings: !compact,
          viewportShowSelectionMode: false,
          viewportShowAnimation: false,
          viewportShowTrajectoryControls: false
        })
        if (!active) {
          viewer.plugin.dispose()
          return
        }

        const backgroundColor = dark ? DARK_BG : LIGHT_BG
        viewer.plugin.canvas3d?.setProps({
          renderer: { backgroundColor: backgroundColor as never }
        })

        await viewer.loadStructureFromData(
          data,
          format === 'cif' ? 'mmcif' : format
        )

        // Re-apply after load — some presets reset clear color.
        viewer.plugin.canvas3d?.setProps({
          renderer: { backgroundColor: backgroundColor as never }
        })
      })
      .catch(cause => {
        if (active) {
          setError(
            cause instanceof Error ? cause.message : 'Unable to load structure'
          )
        }
      })

    return () => {
      active = false
      viewer?.plugin.dispose()
    }
  }, [compact, data, dark, format])

  if (error) {
    return (
      <div
        className={
          compact
            ? 'text-muted-foreground grid h-full place-items-center p-2 text-[10px]'
            : 'text-destructive grid h-full min-h-80 place-items-center p-6 text-sm'
        }
      >
        {compact ? 'Preview unavailable' : error}
      </div>
    )
  }

  return (
    <div
      className={
        dark
          ? compact
            ? 'structure-viewer-dark pointer-events-none relative h-full w-full overflow-hidden bg-[#08080a]'
            : 'structure-viewer-dark relative h-full min-h-80 w-full overflow-hidden bg-[#08080a]'
          : compact
            ? 'structure-viewer-light pointer-events-none relative h-full w-full overflow-hidden bg-white'
            : 'structure-viewer-light relative h-full min-h-80 w-full overflow-hidden bg-white'
      }
    >
      <style>{`
        .structure-viewer-dark .msp-plugin,
        .structure-viewer-dark .msp-plugin-content,
        .structure-viewer-dark .msp-layout-standard,
        .structure-viewer-dark .msp-layout-main,
        .structure-viewer-dark .msp-viewport,
        .structure-viewer-dark .msp-viewport-wrap {
          background: #08080a !important;
          border: none !important;
          box-shadow: none !important;
          outline: none !important;
          color: #e4e4e7 !important;
        }
        .structure-viewer-dark .msp-viewport-controls,
        .structure-viewer-dark .msp-viewport-controls-buttons,
        .structure-viewer-dark .msp-semi-transparent-background {
          background: rgba(24, 24, 27, 0.92) !important;
          border-color: rgba(63, 63, 70, 0.8) !important;
          color: #e4e4e7 !important;
          box-shadow: none !important;
        }
        .structure-viewer-dark .msp-btn,
        .structure-viewer-dark .msp-btn-link,
        .structure-viewer-dark .msp-btn-icon,
        .structure-viewer-dark .msp-btn-icon-small,
        .structure-viewer-dark button {
          background: transparent !important;
          color: #d4d4d8 !important;
          border-color: transparent !important;
        }
        .structure-viewer-dark .msp-btn:hover,
        .structure-viewer-dark .msp-btn-icon:hover,
        .structure-viewer-dark .msp-btn-icon-small:hover,
        .structure-viewer-dark button:hover {
          background: rgba(63, 63, 70, 0.7) !important;
          color: #fafafa !important;
        }
        .structure-viewer-dark .msp-btn svg,
        .structure-viewer-dark .msp-btn-icon svg,
        .structure-viewer-dark .msp-btn-icon-small svg {
          fill: currentColor !important;
          stroke: currentColor !important;
          color: inherit !important;
        }
        .structure-viewer-dark .msp-highlight-toast-wrapper,
        .structure-viewer-dark .msp-scrollable-container,
        .structure-viewer-dark .msp-control-group-wrapper,
        .structure-viewer-dark .msp-control-group-header,
        .structure-viewer-dark .msp-panel,
        .structure-viewer-dark .msp-section-header {
          background: #18181b !important;
          color: #e4e4e7 !important;
          border-color: #3f3f46 !important;
        }

        /* Light mode: strip Mol* viewport borders (grid + full preview). */
        .structure-viewer-light .msp-plugin,
        .structure-viewer-light .msp-plugin-content,
        .structure-viewer-light .msp-layout-standard,
        .structure-viewer-light .msp-layout-main,
        .structure-viewer-light .msp-viewport,
        .structure-viewer-light .msp-viewport-wrap,
        .structure-viewer-light .msp-plugin3d,
        .structure-viewer-light canvas {
          background: #ffffff !important;
          border: none !important;
          box-shadow: none !important;
          outline: none !important;
        }
        .structure-viewer-light .msp-viewport-controls,
        .structure-viewer-light .msp-viewport-controls-buttons,
        .structure-viewer-light .msp-semi-transparent-background {
          border: none !important;
          box-shadow: none !important;
        }
      `}</style>
      <div ref={hostRef} className="absolute inset-0" />
    </div>
  )
}
