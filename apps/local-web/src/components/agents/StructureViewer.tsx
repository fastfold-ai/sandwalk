import 'molstar/build/viewer/molstar.css'

import { useEffect, useRef, useState } from 'react'

const DARK_BG = 0x08080a
const LIGHT_BG = 0xffffff

type MolstarViewer = import('molstar/lib/apps/viewer/app').Viewer

function isDocumentDark() {
  return (
    typeof document !== 'undefined' &&
    document.documentElement.classList.contains('dark')
  )
}

function applyViewerBackground(viewer: MolstarViewer, dark: boolean) {
  const backgroundColor = dark ? DARK_BG : LIGHT_BG
  viewer.plugin.canvas3d?.setProps({
    renderer: { backgroundColor: backgroundColor as never }
  })
}

/**
 * Mol* registers custom-prop symbols on a process-global QueryRuntimeTable.
 * Creating another Viewer re-adds the same symbols and logs noisy warnings.
 * Mute only that known Mol* message.
 */
async function createViewerMuted(
  host: HTMLElement,
  options: Parameters<
    typeof import('molstar/lib/apps/viewer/app').Viewer.create
  >[1]
) {
  const { Viewer } = await import('molstar/lib/apps/viewer/app')
  const originalWarn = console.warn
  console.warn = (...args: unknown[]) => {
    const message = typeof args[0] === 'string' ? args[0] : ''
    if (
      message.includes('already added') &&
      message.includes('removeSymbol/removeCustomProps')
    ) {
      return
    }
    originalWarn.apply(console, args as Parameters<typeof console.warn>)
  }
  try {
    return await Viewer.create(host, options)
  } finally {
    console.warn = originalWarn
  }
}

/**
 * Mol*'s renderReact18 does createRoot(target) and never unmounts.
 * Always pass a fresh child node so we never call createRoot twice on the
 * same container (which throws in React 18).
 */
function createFreshMountNode(host: HTMLElement) {
  const mount = document.createElement('div')
  mount.style.width = '100%'
  mount.style.height = '100%'
  host.replaceChildren(mount)
  return mount
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
  const viewerRef = useRef<MolstarViewer | null>(null)
  const [viewerReady, setViewerReady] = useState(0)
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

  // Create the Mol* viewer once per mount/compact mode.
  useEffect(() => {
    if (!hostRef.current) return
    let active = true
    let viewer: MolstarViewer | null = null
    const host = hostRef.current
    const mount = createFreshMountNode(host)

    void (async () => {
      try {
        viewer = await createViewerMuted(mount, {
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
          viewer.dispose()
          return
        }
        viewerRef.current = viewer
        applyViewerBackground(viewer, isDocumentDark())
        setViewerReady(value => value + 1)
      } catch (cause) {
        if (active) {
          setError(
            cause instanceof Error ? cause.message : 'Unable to load structure'
          )
        }
      }
    })()

    return () => {
      active = false
      viewerRef.current = null
      viewer?.dispose()
      // Drop the node that owned the React root so the next createRoot is clean.
      host.replaceChildren()
    }
  }, [compact])

  // Reload structure on the existing viewer — never recreate the React root.
  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer || viewerReady === 0) return
    let active = true

    void (async () => {
      try {
        setError(null)
        await viewer.plugin.clear()
        if (!active) return
        await viewer.loadStructureFromData(
          data,
          format === 'cif' ? 'mmcif' : format
        )
        if (!active) return
        applyViewerBackground(viewer, isDocumentDark())
      } catch (cause) {
        if (active) {
          setError(
            cause instanceof Error ? cause.message : 'Unable to load structure'
          )
        }
      }
    })()

    return () => {
      active = false
    }
  }, [data, format, viewerReady])

  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    applyViewerBackground(viewer, dark)
  }, [dark, viewerReady])

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
            ? 'structure-viewer-dark structure-viewer-compact pointer-events-none relative h-full w-full overflow-hidden bg-[#08080a]'
            : 'structure-viewer-dark relative h-full min-h-80 w-full overflow-hidden bg-[#08080a]'
          : compact
            ? 'structure-viewer-light structure-viewer-compact pointer-events-none relative h-full w-full overflow-hidden bg-white'
            : 'structure-viewer-light relative h-full min-h-80 w-full overflow-hidden bg-white'
      }
    >
      <style>{`
        .structure-viewer-compact .msp-viewport-controls,
        .structure-viewer-compact .msp-viewport-controls-buttons,
        .structure-viewer-compact .msp-highlight-toast-wrapper,
        .structure-viewer-compact .msp-logo,
        .structure-viewer-compact .msp-image-wrapper {
          display: none !important;
        }

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
