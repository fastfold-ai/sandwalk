import { ArrowUp, Loader2, X } from 'lucide-react'

import { VoiceLevelBars } from '@/components/agents/composer/VoiceLevelBars'
import { cn } from '@/lib/utils'

export function ComposerVoiceBar({
  recording,
  transcribing,
  levels,
  onCancel,
  onConfirm
}: {
  recording: boolean
  transcribing: boolean
  levels: number[]
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <div
      className="flex min-h-12 items-center gap-2 px-1.5 py-1"
      role="status"
      aria-live="polite"
    >
      <button
        type="button"
        onClick={onCancel}
        disabled={transcribing}
        className={cn(
          'grid size-8 shrink-0 place-items-center rounded-full',
          'bg-white/10 text-white/90 hover:bg-white/15',
          'disabled:pointer-events-none disabled:opacity-40'
        )}
        aria-label="Cancel dictation"
        title="Cancel"
      >
        <X className="size-4" strokeWidth={2.25} />
      </button>

      <div className="flex min-w-0 flex-1 items-center justify-center gap-2.5">
        {transcribing ? (
          <>
            <Loader2 className="size-4 shrink-0 animate-spin text-white/45" />
            <span className="text-[15px] text-white/55">Transcribing</span>
          </>
        ) : (
          <>
            <VoiceLevelBars levels={levels} className="text-white/45" />
            <span className="text-[15px] text-white/55">Listening</span>
          </>
        )}
      </div>

      <button
        type="button"
        onClick={onConfirm}
        disabled={transcribing || !recording}
        className={cn(
          'grid size-8 shrink-0 place-items-center rounded-full',
          'bg-white text-black hover:bg-white/90',
          'disabled:pointer-events-none disabled:opacity-40'
        )}
        aria-label={recording ? 'Stop and transcribe' : 'Transcribing'}
        title={recording ? 'Stop and transcribe' : 'Transcribing'}
      >
        <ArrowUp className="size-4" strokeWidth={2.5} />
      </button>
    </div>
  )
}
