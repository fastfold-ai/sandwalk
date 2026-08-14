import { CircleCheck, Loader } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type ModalField = {
  envVar: string
  label: string
  isSecret: boolean
  configured: boolean
  source: string
  maskedPreview: string | null
}

export function SandboxModalSection({
  modalReady,
  modalFields,
  tokenDrafts,
  formDisabled,
  savingTokens,
  probeOk,
  probeDetail,
  busy,
  overlayMessage,
  tokenDirty,
  onTokenDraftChange,
  onClearModalTokens,
  onRunProbe,
  onSaveModalTokens,
  canProbe,
  canSaveTokens
}: {
  modalReady: boolean
  modalFields: ModalField[]
  tokenDrafts: Record<string, string>
  formDisabled: boolean
  savingTokens: boolean
  probeOk: boolean
  probeDetail: string | null
  busy: boolean
  overlayMessage: string | null
  tokenDirty: boolean
  onTokenDraftChange: (envVar: string, value: string) => void
  onClearModalTokens: () => void
  onRunProbe: () => void
  onSaveModalTokens: () => void
  canProbe: boolean
  canSaveTokens: boolean
}) {
  return (
    <section className="space-y-4">
      <div>
        <h3 className="text-base font-semibold">Modal credentials</h3>
        <p className="text-muted-foreground mt-1 text-sm">
          Required before chats can start Modal Sandbox.
        </p>
      </div>

      {!modalReady ? (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2.5 text-sm text-amber-900 dark:text-amber-200">
          Modal is not set up. Enter and save your credentials below to enable
          Modal Sandbox in chats.
        </div>
      ) : null}

      <div className="overflow-hidden rounded-md border">
        <div className="bg-muted/20 text-muted-foreground grid grid-cols-[minmax(9.5rem,0.9fr)_minmax(0,1.4fr)_minmax(7.5rem,0.85fr)_4.5rem] items-center gap-3 border-b px-3 py-2 text-xs">
          <span>Key</span>
          <span>Value</span>
          <span>Status</span>
          <span className="text-right">Action</span>
        </div>
        {modalFields.map(field => (
          <div
            key={field.envVar}
            className="grid grid-cols-[minmax(9.5rem,0.9fr)_minmax(0,1.4fr)_minmax(7.5rem,0.85fr)_4.5rem] items-center gap-3 border-b px-3 py-3 last:border-b-0"
          >
            <div className="min-w-0">
              <strong className="block truncate text-sm">{field.envVar}</strong>
              <span className="text-muted-foreground block truncate text-xs">
                {field.label}
              </span>
            </div>
            <Input
              type={field.isSecret ? 'password' : 'text'}
              value={tokenDrafts[field.envVar] || ''}
              disabled={formDisabled || savingTokens}
              className="min-w-0 w-full"
              onChange={event =>
                onTokenDraftChange(field.envVar, event.target.value)
              }
              placeholder={`Enter ${field.envVar}`}
            />
            <span className="text-muted-foreground min-w-0 truncate text-xs">
              {field.configured
                ? `Configured · ${field.maskedPreview || field.source}`
                : 'Not configured'}
            </span>
            {field.configured ? (
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive justify-self-end"
                disabled={formDisabled || savingTokens}
                onClick={() => onClearModalTokens()}
              >
                Remove
              </Button>
            ) : (
              <span className="text-muted-foreground justify-self-end px-1">
                -
              </span>
            )}
          </div>
        ))}
      </div>

      {probeOk ? (
        <p className="text-sm text-emerald-700 dark:text-emerald-400">
          {probeDetail || 'Probe healthy.'}
        </p>
      ) : probeDetail ? (
        <p className="text-muted-foreground text-sm">{probeDetail}</p>
      ) : null}

      <div className="flex flex-wrap items-center justify-end gap-2">
        <Button
          variant="secondary"
          disabled={formDisabled || savingTokens || !modalReady || !canProbe}
          onClick={() => onRunProbe()}
        >
          {busy && overlayMessage?.startsWith('Probing') ? (
            <Loader className="size-4 animate-spin" />
          ) : (
            <CircleCheck className="size-4" />
          )}
          Test
        </Button>
        <Button
          disabled={
            formDisabled || savingTokens || !tokenDirty || !canSaveTokens
          }
          onClick={() => onSaveModalTokens()}
        >
          {savingTokens ? <Loader className="animate-spin" /> : null}
          Save
        </Button>
      </div>
    </section>
  )
}

export function defaultModalFields(): ModalField[] {
  return [
    {
      envVar: 'MODAL_TOKEN_ID',
      label: 'Modal Token ID',
      isSecret: false,
      configured: false,
      source: 'none',
      maskedPreview: null
    },
    {
      envVar: 'MODAL_TOKEN_SECRET',
      label: 'Modal Token Secret',
      isSecret: true,
      configured: false,
      source: 'none',
      maskedPreview: null
    }
  ]
}
