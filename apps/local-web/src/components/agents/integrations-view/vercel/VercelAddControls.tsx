import { ChevronDown, KeyRound, Loader2, Plus } from 'lucide-react'
import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'

import { VERCEL_ADD_HEADER_SLOT_ID } from '../integrations-view-detail-header'
import { VercelOidcModal } from './VercelOidcModal'

export function VercelAddControls({
  busy,
  configured,
  setupUrl,
  onSaveToken,
  onRunTerminal
}: {
  busy: boolean
  configured: boolean
  setupUrl?: string | null
  onSaveToken: (token: string) => Promise<void>
  onRunTerminal: () => void
}) {
  const [modalOpen, setModalOpen] = useState(false)
  const [headerSlot, setHeaderSlot] = useState<Element | null>(null)

  useEffect(() => {
    setHeaderSlot(document.getElementById(VERCEL_ADD_HEADER_SLOT_ID))
  }, [])

  const addButton = (
    <div className="inline-flex items-stretch">
      <Button
        size="sm"
        className="h-8 gap-1.5 rounded-r-none"
        disabled={busy}
        onClick={onRunTerminal}
      >
        {busy ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <Plus className="size-3.5" />
        )}
        Add
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            size="sm"
            className="h-8 rounded-l-none border-l border-l-black/10 px-2 dark:border-l-white/15"
            disabled={busy}
            aria-label="More Vercel add options"
          >
            <ChevronDown className="size-3.5" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuItem onSelect={() => setModalOpen(true)}>
            <KeyRound className="size-3.5" />
            Add Vercel OIDC (manual)
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )

  return (
    <>
      {headerSlot != null ? createPortal(addButton, headerSlot) : null}
      <VercelOidcModal
        open={modalOpen}
        busy={busy}
        configured={configured}
        setupUrl={setupUrl}
        onOpenChange={setModalOpen}
        onSaveToken={onSaveToken}
        onRunTerminal={onRunTerminal}
      />
    </>
  )
}
