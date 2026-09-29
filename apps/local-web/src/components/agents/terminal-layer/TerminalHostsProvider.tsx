import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { TerminalSession } from '@sandwalk/agent-ui-core'

import { TerminalPortalHost } from './TerminalPortalHost'

/**
 * FAS-107 W1: monta un `TerminalPortalHost` por cada terminal
 * conocido.
 *
 * Vive a nivel de `AppShellMain` (arriba del split y de la ruta
 * `/terminals/:id`) para que los hosts sobrevivan a cualquier cambio
 * de layout / navegación / foco.
 *
 * Cada host es responsable de sí mismo — se posiciona sobre el
 * placeholder cuando existe, se oculta cuando no. Cuando el terminal
 * desaparece de `terminals` (usuario lo cerró explícitamente), el
 * host se desmonta y libera el xterm.
 */
export function TerminalHostsProvider({
  client,
  terminals
}: {
  client: LocalAgentClient
  terminals: TerminalSession[]
}) {
  return (
    <>
      {terminals.map(term => (
        <TerminalPortalHost
          key={term.id}
          client={client}
          terminalId={term.id}
        />
      ))}
    </>
  )
}
