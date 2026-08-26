import type {
  AgentSession,
  SessionGroup,
  TerminalSession
} from '@sandwalk/agent-ui-core'

/**
 * FAS-107 X5.3 · Sistema de tipos discriminados para items del strip.
 *
 * PROBLEMA DE RAÍZ (jornada X4.4 · 10 hotfixes):
 * Sandwalk maneja items polimórficos en el strip / sidebar / split
 * (`chat`, `terminal`, `group`, y potencialmente `note`, `canvas`, `mcp`
 * en el futuro). Cada consumidor hacía su propio `if (id.startsWith('term_'))`
 * y era fácil olvidarse de un tipo. Los últimos 10 hotfixes fueron todos
 * variantes del mismo patrón: "consumidor X no reconoció tipo Y".
 *
 * SOLUCIÓN (patrón VSCode `EditorInput` + Excalidraw `ExcalidrawElement`):
 *
 * - **Discriminated union** por campo `kind`. TypeScript garantiza
 *   narrow correcto al hacer `if (item.kind === 'terminal')`.
 * - **`assertNever`** en el `default` de cada `switch (item.kind)`. Si
 *   alguien agrega un `kind` nuevo al union, TypeScript rompe el build
 *   en TODOS los sitios que no lo contemplaron. La disciplina deja de
 *   depender del dev; el compilador es el guardián.
 * - **Resolver único** (`resolveStripItem`) que dado un id busca en
 *   las 3 fuentes y devuelve el `StripItem` tipado. Los consumidores
 *   consultan este resolver en vez de hacer sus propios switches por
 *   prefijo.
 *
 * REFERENTES:
 * - VSCode `EditorInput` + Registry pattern.
 * - Excalidraw `ExcalidrawElement` discriminated union.
 * - Windows Terminal `ControlCore/Interactivity/Control` (separación
 *   core / interactivity / view).
 *
 * EXTENSIBILIDAD:
 * Agregar `note`, `canvas`, `mcp` en el futuro requiere:
 * 1. Agregar la rama al `StripItem` union.
 * 2. Actualizar `resolveStripItem` con la nueva fuente.
 * 3. TypeScript señala automáticamente cada switch que necesita cubrir
 *    el nuevo `kind`. Cero búsqueda manual.
 */

/**
 * Todos los tipos que pueden aparecer como chip en el strip o como
 * item dentro de un grupo/split.
 */
export type StripItemKind = 'chat' | 'terminal' | 'group'

/**
 * StripItem discriminado. La rama `kind` narrowea automáticamente al
 * tipo específico dentro del `if`/`switch`.
 */
export type StripItem =
  | { kind: 'chat'; id: string; session: AgentSession }
  | { kind: 'terminal'; id: string; terminal: TerminalSession }
  | { kind: 'group'; id: string; group: SessionGroup }

/**
 * Exhaustive checker. Cada `switch (item.kind)` debe cerrar con
 * `default: return assertNever(item)`. Si alguien agrega un `kind` al
 * union, TypeScript señala este sitio con "Argument of type 'X' is
 * not assignable to parameter of type 'never'".
 *
 * @example
 * function labelFor(item: StripItem): string {
 *   switch (item.kind) {
 *     case 'chat': return item.session.title
 *     case 'terminal': return item.terminal.title
 *     case 'group': return item.group.name
 *     default: return assertNever(item)
 *   }
 * }
 */
export function assertNever(value: never): never {
  throw new Error(
    `assertNever: unhandled discriminated union case: ${JSON.stringify(value)}`
  )
}

/**
 * Fuentes de datos que el resolver consulta. Deliberadamente maps para
 * lookup O(1) — el resolver puede llamarse en loops (por ejemplo al
 * mapear openTabIds en el strip).
 */
export type StripItemSources = {
  sessionsById: Map<string, AgentSession>
  terminalsById: Map<string, TerminalSession>
  groupsById: Map<string, SessionGroup>
}

/**
 * Resolver único: dado un id polimórfico, retorna el `StripItem`
 * tipado o `null` si el id no matchea ninguna fuente.
 *
 * Prioridad de resolución:
 * 1. Grupo (evita colisiones si accidentalmente un `grp_*` llegara a
 *    `sessionsById`).
 * 2. Terminal.
 * 3. Chat.
 *
 * NUNCA hace switch por prefijo (`id.startsWith`). El registro real de
 * los ids está en los stores; el prefijo del id es solo debug.
 */
export function resolveStripItem(
  id: string,
  sources: StripItemSources
): StripItem | null {
  const group = sources.groupsById.get(id)
  if (group) return { kind: 'group', id, group }

  const terminal = sources.terminalsById.get(id)
  if (terminal) return { kind: 'terminal', id, terminal }

  const session = sources.sessionsById.get(id)
  if (session) return { kind: 'chat', id, session }

  return null
}

/**
 * Sólo el kind (para consumidores que no necesitan la data). Útil para
 * `if (getStripItemKind(id, sources) === 'terminal') …` en lugares
 * donde solo importa el tipo.
 */
export function getStripItemKind(
  id: string,
  sources: StripItemSources
): StripItemKind | null {
  return resolveStripItem(id, sources)?.kind ?? null
}

/**
 * Helper: convierte listas a los maps que espera el resolver. Los
 * consumers típicamente tienen `sessions`, `terminals`, `tabGroups`
 * como arrays.
 */
export function buildStripItemSources(input: {
  sessions: AgentSession[]
  terminals: TerminalSession[]
  tabGroups: SessionGroup[]
}): StripItemSources {
  return {
    sessionsById: new Map(input.sessions.map(s => [s.id, s])),
    terminalsById: new Map(input.terminals.map(t => [t.id, t])),
    groupsById: new Map(input.tabGroups.map(g => [g.id, g]))
  }
}

/**
 * Helper narrowing con `assertNever` embebido. Sirve como template
 * para consumidores que rendean UI polimórfica.
 *
 * @example
 * const icon = matchStripItem(item, {
 *   chat: () => <MessageSquare />,
 *   terminal: () => <SquareTerminal />,
 *   group: () => <Columns2 />
 * })
 */
export function matchStripItem<T>(
  item: StripItem,
  handlers: {
    chat: (session: AgentSession, id: string) => T
    terminal: (terminal: TerminalSession, id: string) => T
    group: (group: SessionGroup, id: string) => T
  }
): T {
  switch (item.kind) {
    case 'chat':
      return handlers.chat(item.session, item.id)
    case 'terminal':
      return handlers.terminal(item.terminal, item.id)
    case 'group':
      return handlers.group(item.group, item.id)
    default:
      return assertNever(item)
  }
}
