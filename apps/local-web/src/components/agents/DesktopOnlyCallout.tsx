import { Monitor } from 'lucide-react'

/** Gate for menubar/Tauri-only actions. */
export function DesktopOnlyCallout({
  feature = 'This feature'
}: {
  feature?: string
}) {
  return (
    <div className="bg-muted/40 flex items-start gap-3 rounded-xl border px-4 py-3 text-sm">
      <Monitor className="text-muted-foreground mt-0.5 size-4 shrink-0" />
      <div>
        <p className="font-medium">{feature} is available in the Sandwalk desktop app.</p>
        <p className="text-muted-foreground mt-1">
          Open Sandwalk from the menu bar (Settings… or Open Web Dashboard) to
          manage the local agent process and desktop preferences.
        </p>
      </div>
    </div>
  )
}
