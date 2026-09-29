/**
 * FAS-107 · Fase 1a · thin wrapper sobre `session-attention.ts`.
 *
 * Antes vivía como un bus paralelo con su propio Set y listeners:
 * chats disparaban dot azul via `session-attention` (Dock badge +
 * filtro Bell), terminales disparaban dot naranja via este módulo
 * sin tocar Dock ni filtro. El usuario tenía "dos colas de atención"
 * con semántica distinta.
 *
 * Ahora los terminales viven en el MISMO bus que los chats: un solo
 * Set, un solo color de dot (azul), Dock badge y filtro Unread los
 * cuentan/listan juntos. Splits reciben la señal si cualquier hijo
 * (chat o terminal) está en attention.
 *
 * Los símbolos originales se conservan por compatibilidad —
 * cualquier caller sigue funcionando sin cambios, pero por debajo
 * llama al bus unificado.
 */

import { useEffect, useState } from 'react'

import {
  clearSessionAttention,
  getAttentionSessionIds,
  markSessionAttention,
  SESSION_ATTENTION_CHANGE_EVENT
} from '@/lib/session-attention'

export function markTerminalActivity(terminalId: string): void {
  markSessionAttention(terminalId)
}

export function clearTerminalActivity(terminalId: string): void {
  clearSessionAttention(terminalId)
}

/** True when this terminal has unseen output (unificado con chats). */
export function useTerminalHasActivity(terminalId: string): boolean {
  const [has, setHas] = useState<boolean>(() =>
    getAttentionSessionIds().has(terminalId)
  )
  useEffect(() => {
    const onChange = () => setHas(getAttentionSessionIds().has(terminalId))
    onChange()
    window.addEventListener(SESSION_ATTENTION_CHANGE_EVENT, onChange)
    return () => {
      window.removeEventListener(SESSION_ATTENTION_CHANGE_EVENT, onChange)
    }
  }, [terminalId])
  return has
}
