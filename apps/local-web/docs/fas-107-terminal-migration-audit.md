# FAS-107 · Auditoría de terminales-en-splits y plan de migración

> Documento vivo. Origen: quejas del usuario sobre "menús contextuales que no aparecen", "terminal vacío al agregar a split", "chip Hi que no cierra", y "no se nota solidez en el desarrollo".
> Consolidado con investigación en referentes (VSCode, Warp, Hyper, Windows Terminal, xterm.js, Tauri v2) y auditoría del código del branch `tony/fas-107-add-terminal-view-in-grid`.

---

## 1 · Contexto

Sandwalk es una app **Tauri v2 Mac** (WKWebView + React + backend Python spawneado en el mismo proceso). Cerrar la app con Cmd+Q mata también el backend Python; no hay reconexión desde otro cliente ni multi-usuario.

El sistema de sesiones tiene tres tipos de items polimórficos:

- **Chats** (`chat_xxx`) — sesiones de agente con mensajes + composer.
- **Terminales** (`term_xxx`) — sesiones PTY con xterm.js.
- **Splits** (`grp_xxx`) — contenedores que agrupan varios chats/terminales en panes lado a lado, con layout resizable.

Estos tres coexisten en:

- **Strip** (`SessionTabs`) — la barra de tabs superior. Cada chip es un chat, terminal o split.
- **Sidebar** (`AppShellSidebar` + `sidebar-session-list`) — la lista lateral.
- **Main panel** (`AgentSessionMainPanel`) — el área grande que renderea según la URL.
- **Layer flotante** (`TerminalLayerRoot` + `TerminalHostsProvider`) — sistema paralelo donde viven los xterm reales. Cada `TerminalPortalHost` se posiciona sobre un `TerminalPlaceholder` con `getBoundingClientRect()`.

## 2 · Alcance de la auditoría

**Sí cubre:**
- Estado, ciclo de vida y sincronía de la lista de terminales.
- Menús contextuales y su convivencia con el layer flotante.
- Handlers duplicados chat/terminal.
- Persistencia de tabs y grupos ante Cmd+Q → reopen.
- Rutas ambiguas y navegación entre tipos.

**No cubre (fuera de scope):**
- Backend Python (contratos del PTY, WebSocket, filesystem).
- `agent-ui-core` (tipos base sin cambios).
- Otras features del shell (Dashboard, Projects, Library).

---

## 3 · Diagnóstico consolidado

### 3.1 Top 5 causas raíz

| # | Causa | Bugs que explica | Ubicación |
|---|---|---|---|
| 1 | **Doble `useAppTerminals`** — dos fuentes de verdad para "qué terminales existen" | Terminal vacío en split (A), negro vacío en `/terminals/:id` (C), UI desincronizada | `App.tsx:76` + `AgentSessionMainPanel.tsx:281` |
| 2 | **`openSessionTab` faltante** en `handlePickTerminal`, `handleAddChatToSplit`, `handleRemoveChatFromSplit` | Survivor invisible al disolver split (B), tab fantasma al crear terminal | `App.tsx:512-582`, `AgentSessionMainPanel.tsx:293-319` |
| 3 | **Handlers duplicados con lógica divergente** | Cerrar/mover/renombrar desde strip vs sidebar produce efectos distintos | `handleCloseTerminal` local + `handleDeleteTerminalGlobal`; `handleToggleTerminalOrganizeLabel` × 2; `handleMoveTerminalToProject` × 2 |
| 4 | **Pending groups persistidos sin cleanup al bootstrap** | Chip "Hi" huérfano que no cierra ni abre | `useAppTabGroups.ts:157-168` guarda a `writeTabGroups`; ningún consumidor barre huérfanos |
| 5 | **Layer flotante come eventos** | Context menu no aparece sobre terminales; foco flickerea | `TerminalPortalHost.tsx:111-116` con `pointer-events:auto` sobre placeholder; `Terminal.open()` re-llamado en reparent |

### 3.2 Asimetrías de paridad chat vs terminal

- Strip: chat tiene "Create split view" en el menú; terminal no.
- Strip: group no tiene Pin/Unpin ni Move to project.
- Sidebar: chip de group no tiene "Close tab" (strip sí).
- Sidebar: "Delete" del child terminal en split borra el terminal globalmente (destructivo). El equivalente para chat distingue "delete real" de "remove from split".

### 3.3 Ambigüedad de rutas

`/agents/:id` acepta `chat_`, `grp_` y `term_` sin distinción. `isReservedAgentRouteId` no filtra prefijos, y cada consumidor hace su propio `startsWith(...)` de forma repetida. Un `term_` que caiga en `/agents/` no se detecta automáticamente.

---

## 4 · Investigación de patrones

### 4.1 Terminales-en-splits (VSCode, Warp, Hyper, Windows Terminal, xterm.js)

**Patrón oficial confirmado del equipo de xterm.js: `Terminal.open()` una sola vez.** Los issues [#4978](https://github.com/xtermjs/xterm.js/issues/4978) y [#1323](https://github.com/xtermjs/xterm.js/issues/1323) documentan que un segundo `open()` no renderea y pierde el theme. Para mover el xterm entre contenedores, el patrón es:

```
newContainer.appendChild(term.element)   // el buffer vive en term.element
fitAddon.fit()                            // refit al nuevo tamaño
```

VSCode lo implementa así en `terminalInstance.ts` con un guard `_attached` (`if (!this._attached) this.raw.open(container)`). Nuestro código actual en `TerminalPortalHost.tsx:170` llama `term.open(host)` en cada mount del hostNode. Con la implementación de layer estable (un host único por terminal) esto solo ocurre una vez, así que **no es un bug activo hoy**, pero la línea "V1c" del changelog reciente indica que ya nos mordió durante iteración. El patrón debe quedar explícito.

**React portal + contextmenu.** La [doc oficial de React](https://react.dev/reference/react-dom/createPortal) confirma:

> *"Events from portals propagate according to the React tree rather than the DOM tree."*

Es decir: `onContextMenu` en un ancestor React del portal **sí** recibe el evento cuando ocurre en el DOM del portal, siempre que el nodo se rendere via `createPortal` desde ese ancestor. **Nuestro `TerminalPortalHost` sí usa `createPortal`**, por lo tanto el evento debería propagarse. El bug del context menu proviene de **otro sitio**: el `TerminalPlaceholder` tiene `pointer-events:auto` a través del portal host, y el layer captura `mousedown` con `addEventListener` nativo que no propaga hacia el árbol React. Solución: registrar `contextmenu` en un **wrapper propio** dentro del portal (patrón VSCode `_tabContainer`) y despachar al menú del pane.

**`pointer-events` correcto.** El placeholder debe ser `pointer-events: none` (solo reserva layout). El host flotante `pointer-events: auto` sobre el área xterm. El wrapper React del pane conserva sus handlers (`onMouseDownCapture`, `onContextMenu`) que reciben el evento delegado.

**ResizeObserver.** No recrear en cada notify. Un solo observer por sesión + `requestAnimationFrame` + debounce 150-200ms antes de `fit.fit()` y envío al PTY. Recomendación oficial en [xterm.js #3564](https://github.com/xtermjs/xterm.js/issues/3564).

**Focus en splits.** Windows Terminal y VSCode usan estado propio `activeLeafId` en el store del split, NO `document.activeElement`. Al cambiar de pane, `terminal.focus()` explícito sobre el leaf activo.

### 4.2 Single source of truth (Zustand, TanStack Query, useSyncExternalStore)

**Recomendación: Zustand store singleton con selectores atómicos y actions tipadas.**

Criterio:

1. **Coherencia con el repo.** Ya usamos Zustand para `useAppTabGroups`. No agrega dependencia nueva ni modelo mental nuevo.
2. **Ataca la causa raíz #1 directamente.** Un solo `TerminalsStore` accesible desde cualquier componente sin prop drilling ni duplicación de hooks.
3. **Bundle mínimo** (~3KB) sin Provider.
4. **TanStack Query no aplica.** Su caso de uso principal (server state con latencia de red + cache invalidation cross-cliente) no existe en Tauri con backend in-process.
5. **`useOptimistic` de React 19 no aplica.** Es component-local; no propaga entre consumidores.

**Patrón oficial** ([TkDodo · Working with Zustand](https://tkdodo.eu/blog/working-with-zustand)):

```
useTerminalsStore.getState().terminals              // acceso imperativo
useTerminalsStore(state => state.terminals)         // suscripción reactiva
useTerminalsStore(state => state.terminals.find(...), shallow)  // selector atómico
```

Cada consumidor se suscribe **solo a la slice que necesita**:

- `TerminalHostsProvider` → `state.terminals` (necesita todos los ids).
- `SessionTabs` → `state.terminals.filter(t => openTabIds.includes(t.id))`.
- `TerminalSplitPanelHeader` → `state.terminals.find(t => t.id === terminalId)` (solo su terminal).

**Migración sin regresiones.** Patrón consolidado (TkDodo + Kent C. Dodds):

1. Cubrir con tests el comportamiento observable actual del hook (agregar, optimistic, refresh, remoción).
2. Crear el store nuevo **en paralelo** al hook viejo. La API pública del hook queda igual, pero internamente lee/escribe al store singleton.
3. Migrar consumidor por consumidor con PRs chicos.
4. Borrar el hook viejo cuando ningún consumidor lo usa.

**Optimistic UI.** Snapshot antes → aplicar cambio → mutar → en error rollback, en éxito reconciliar (reemplazar el placeholder con el real).

### 4.3 Tauri Mac (persistence, lifecycle, context menus, WKWebView)

**Persistence.** `tauri-plugin-store` en vez de `localStorage` para state que el backend Python también deba leer (tabs abiertos, workspace activo). Ubicación en Mac: `~/Library/Application Support/<bundle-id>/`. Auto-save debounced con `save()` forzado en `RunEvent::ExitRequested`. Ver [Store plugin](https://v2.tauri.app/plugin/store/).

**Ciclo de vida Cmd+Q.** En Rust, `app.run(|_, event| match event { RunEvent::ExitRequested { api, code, .. } => { ... } })`. Orden correcto: `save_state → kill_python_backend → allow_exit`. Check `code.is_some()` vs `None` para evitar el loop documentado en [Tauri #5500](https://github.com/tauri-apps/tauri/issues/5500).

**No persistir.** Drafts del composer, pending groups no confirmados, scrollback del terminal, popovers abiertos, hover states. Todo esto es efímero y persistirlo genera state huérfano al reopen (el caso del chip "Hi").

**Context menus.** Tauri v2 tiene [Menu API nativa built-in](https://v2.tauri.app/learn/window-menu/). El plugin `tauri-plugin-context-menu` es **solo v1** y el maintainer redirige a la API nativa. Trade-off:

| Aspecto | Nativo Tauri | HTML custom |
|---|---|---|
| Accesibilidad (VoiceOver, atajos) | Gratis | Manual |
| Dark mode | Automático | Sincronizar |
| Cmd+shortcuts | Accelerators | Capturar keydown |
| Iconos SF Symbols | Nativos | Lucide |
| Preview visual (avatares, chips) | No soporta | Sí |
| Propagation en WKWebView portal | N/A (no es DOM) | Requiere cuidado |

**Recomendación de scope:** migrar a nativo las listas planas de acciones (strip chip menu, sidebar row menu, right-click sobre chat/terminal). Dejar HTML solo los que requieren preview visual rico.

**WKWebView quirks confirmados** (además del `window.prompt` ya conocido):

- `alert`/`confirm` devuelven **promise**. Ver [Tauri #12576](https://github.com/tauri-apps/tauri/issues/12576).
- `backdrop-filter` + `transparent: true` puede romperse en DMG bundled. Ver [Tauri #13415](https://github.com/tauri-apps/tauri/issues/13415).
- `overscroll-behavior` CSS no funciona; hay que setear `scrollView.bounces = false` vía callback nativo. Ver [wry #557](https://github.com/tauri-apps/wry/issues/557).
- `focus`/`blur` no burbujean; usar capture phase para delegación.

**Referentes Tauri Mac.** Warp es Rust nativo (no Tauri). Wave Terminal es Electron+Go. Zed es GPUI custom. **Spacedrive** y **Reor** sí son Tauri v2 y usan `tauri-plugin-store` para persistence.

---

## 5 · Plan de migración por fases

Cada fase es un commit independiente. Solo pasa a la siguiente cuando el usuario probó OK. Bosquejo antes de codear cada fase estructural.

**Orden de ejecución acordado** (criterio: desbloqueo primero, estructura después, pulido al final):

1. Fase 4 · Cleanup + pending groups efímeros — *desbloquea chip "Hi" ya*
2. Fase 1 · Zustand store singleton — *la más crítica; todas las siguientes dependen*
3. Fase 2 · `openSessionTab` en 3 paths
4. Fase 3 · Un handler por acción
5. Fase 5 · Layer no come eventos
6. Fase 6a · Paridad HTML de menús + ruta estricta
7. Fase 7 · Solidez visual (header `/terminals/:id`, ResizeObserver)
8. Fase 6b · Migración a native Tauri Menu API

Las secciones a continuación describen las fases en su orden lógico original (por cercanía temática), no en el orden de ejecución.

### Fase 1 · Fuente única de verdad para terminales

**Objetivo:** eliminar la doble instancia de `useAppTerminals`. Crear `useTerminalsStore` (Zustand) como fuente única. Cualquier componente que hoy lee/mutar terminales lo hace via el store.

**Bosquejo del store:**

```
TerminalsStore {
  state: {
    terminals: TerminalSession[]
    isLoading: boolean
  }
  actions: {
    setAll(list)                      // reemplaza (después de refresh del backend)
    addOptimistic(term)               // insert temporal (antes de confirmar)
    commit(tempId, real)              // reemplaza optimistic con el confirmado
    remove(id)                        // elimina
    patch(id, changes)                // update parcial
    refresh()                         // fetch al backend
  }
}
```

**Superficies afectadas:**
- `App.tsx` deja de instanciar `useAppTerminals` local; usa selectores del store.
- `AgentSessionMainPanel.tsx` deja de instanciar `useAppTerminals` local; usa selectores.
- `TerminalHostsProvider` usa `useTerminalsStore(state => state.terminals)`.
- `SessionTabs`, `AppShellSidebar`, `TerminalSplitPanelHeader` usan selectores atómicos.
- `handlePickTerminal` y ⌘⇧T usan `store.addOptimistic(term)` + `store.commit(id, real)` después.

**Riesgo:** cambio grande. Requiere bosquejo detallado antes de tocar código y typecheck estricto.

**Verificación:** crear terminal desde 3 vías (strip, ⌘⇧T, split picker) y verificar que aparece inmediato en las tres superficies.

### Fase 2 · `openSessionTab` en paths de creación y promoción

**Objetivo:** cualquier flujo que resulte en un terminal/chat visible como survivor debe registrarlo en `openTabIds`.

**Cambios:**

- `handlePickTerminal` (`AgentSessionMainPanel.tsx:293`): llamar `openSessionTab(id)` antes de retornar.
- `handleAddChatToSplit` (`App.tsx:564`): llamar `openSessionTab(id)` para el nuevo id.
- `handleRemoveChatFromSplit` (`App.tsx:512`): llamar `openSessionTab(survivor)` antes de navigate cuando el grupo se disuelve.

**Verificación:** crear split chat+terminal, remover chat, el terminal survivor aparece en strip y sidebar.

### Fase 3 · Un handler por acción

**Objetivo:** colapsar handlers duplicados a una sola fuente en `App.tsx` con nombres explícitos.

**Cambios:**

| Reemplazar | Con |
|---|---|
| `handleCloseTerminal` local + `handleDeleteTerminalGlobal` | `deleteTerminalPermanently` (destructivo) + `removeTerminalFromSplit` (no destructivo) |
| `handleToggleTerminalOrganizeLabel` × 2 | Uno solo desde el shell |
| `handleMoveTerminalToProject` × 2 | Uno solo desde el shell |

Cada superficie recibe el handler correcto vía props.

**Verificación:** cerrar terminal desde strip y desde sidebar producen el mismo resultado (destructivo real). Remover del split desde header pane no borra el terminal.

### Fase 4 · Cleanup de state huérfano y decisiones de persistencia

**Objetivo:** eliminar chips huérfanos y evitar persistir state efímero.

**Cambios:**

- **Ya:** en `useAppBootstrap`, tras cargar sessions + terminals + tabGroups, filtrar `openTabIds` contra las tres listas reales. Descartar ids huérfanos.
- **Ya:** `createPendingGroup` no persiste a `writeTabGroups`. El pending vive solo en memoria hasta que se confirma con `promoteToGroup`.

**Decisión tomada: `openTabsByProject` se queda en `localStorage`, NO migrar a `tauri-plugin-store`.**

Razón: los tabs abiertos son *preferencia visual del cliente*, no dato del dominio. Ni chats ni terminales dependen de esa lista para funcionar del lado del backend Python; el backend solo maneja las sesiones reales. Migrar a `tauri-plugin-store` sería sobre-ingeniería para un problema que no tenemos (backend leyendo tabs), y agregaría complejidad IPC async sin beneficio.

`tauri-plugin-store` sí se usará en el futuro para:
- Window state (posición, tamaño) vía `tauri-plugin-window-state`.
- User preferences globales (theme, atajos custom).

Ambos fuera del alcance de este barrido.

**Verificación:** después de un Cmd+Q → reopen con un pending group activo (nunca confirmado), NO debe aparecer chip huérfano.

### Fase 5 · Layer flotante que no come eventos

**Objetivo:** context menu funcional sobre terminales; foco predecible.

**Cambios:**

- **`TerminalPlaceholder`**: `pointer-events: none` (solo reserva layout). Nunca captura clicks.
- **`TerminalPortalHost`**: `pointer-events: auto` solo en el div que renderea xterm. Debe registrar `contextmenu` en un wrapper propio con un `<div onContextMenu>` React (aprovechando la propagación oficial de portal) y despachar al `openPaneContextMenu` del `TerminalLeaf` ancestro.
- Eliminar el doble path de focus (host `onMouseDown` + wrapper `onMouseDownCapture`). Único path: el wrapper recibe el evento vía portal-propagation y llama `focusPanel`.

**Verificación runtime (en app Tauri, NO en Chrome dev):**
- Right-click sobre xterm dispara el menú del pane con Split L/R/U/D + Close.
- Left-click sobre xterm foca el pane inmediato sin flicker.
- Copy/paste con Cmd+C/Cmd+V funciona normal.
- Selección de texto en xterm funciona.

### Fase 6 · Paridad de menús + ruta estricta

**Objetivo:** simetría de acciones chat/terminal en todas las superficies; ruta unívoca por tipo.

**Cambios:**

- Terminal en strip context menu: agregar "Create split view".
- Group en strip: agregar Pin/Unpin y Move to project (si conceptualmente aplica al grupo).
- Sidebar chip de group: agregar "Close tab".
- Child terminal en split (sidebar): distinguir "Remove from split" (default) de "Delete permanently" (destructivo confirmado).
- `isReservedAgentRouteId` bloquea prefijos `term_`.
- Cualquier navigate hacia `/agents/term_xxx` se redirige a `/terminals/:id` con un helper `navigateToSession(id)` centralizado.

**Decisión abierta:** ¿migrar los context menus del strip y sidebar a **native Tauri Menu API**? Trade-offs en la tabla anterior. Estimación: esfuerzo Medium. Beneficio de accesibilidad y dark mode automático. Riesgo bajo (es nativo, no hay quirks de WKWebView).

### Fase 6b · Migración a native Tauri Menu API — DIFERIDA

**Estado:** aprobada por el usuario pero diferida al cierre del barrido X3. Motivo:

- Requiere setup en Rust (`main.rs` con `Menu` builder), IPC JS↔Rust, y probablemente refactor de cada superficie de menú.
- Solo se puede validar en la app Tauri bundled (dev usa WKWebView pero puede diferir en el behavior del menu nativo).
- Los bugs urgentes del usuario ya están cubiertos por Fases 1-5, 6a, 7.
- Beneficio (A11y, dark mode automático, cmd-shortcuts) es de calidad, no de desbloqueo.

Se retoma como conversación aparte con research específico del setup Tauri v2 y validación de dónde se prueba.

### Fase 7 · Solidez visual del layer

**Objetivo:** el terminal se ve "sólido", sin saltos.

**Cambios:**

- Un solo `ResizeObserver` por sesión + debounce 150ms antes de `fit.fit()`.
- Header del `/terminals/:id` solo (fuera de split): reutilizar `TerminalSplitPanelHeader` con `focused: true` fijo. Bosquejo:

```
┌──────────────────────────────────────────────────────────┐
│ ▣  Terminal name                                    ⋯  │  ← 52px
│    ● Simetrik solutions-api           (chip proyecto)   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  [xterm live buffer]                                    │
```

- Explicitar el patrón `_attached` boolean en el `TerminalPortalHost` (aunque hoy con layer estable no es un bug activo, dejar la guard evita regresiones futuras).

---

## 6 · Riesgos y bloqueadores

- **Fase 1** es el cambio más grande. Tocar `App.tsx`, `AgentSessionMainPanel.tsx`, `AppShellMain.tsx`, `app-shell-main-props.ts`, `TerminalHostsProvider.tsx`, y cualquier consumidor de `terminals`. Requiere bosquejo dedicado y tests intermedios.
- **Fase 5** requiere verificación runtime en la app Tauri bundled. Los quirks de WKWebView no se reproducen en Chrome dev.
- **Fase 6** decisión abierta sobre native menu vs HTML. Requiere alineación con el usuario antes de codear.
- **Fase 4** solo elimina el chip "Hi" si es un pending group persistido. Si es otra causa (menos probable según el análisis), hay que investigar in situ tras la fase.
- **StrictMode double-mount** puede sorprender al store si las acciones son idempotentes solo por casualidad. Cada action debe ser explícitamente idempotente.

---

## 7 · Checklist de verificación por fase

Cada fase termina con:

- [ ] `pnpm typecheck` en verde.
- [ ] `pnpm test` en verde (los tests que ya existen para el hook migrado).
- [ ] Verificación runtime en la app Tauri (no Chrome dev) para bugs de WKWebView.
- [ ] Casos de prueba manuales listados en el mensaje de commit.
- [ ] User aprueba antes de pasar a la siguiente fase.

---

## 8 · Fuentes

**Portal terminals y xterm.js:**
- [React · createPortal](https://react.dev/reference/react-dom/createPortal)
- [xterm.js · Terminal API](https://xtermjs.org/docs/api/terminal/classes/terminal/) · [#4978](https://github.com/xtermjs/xterm.js/issues/4978) · [#1323](https://github.com/xtermjs/xterm.js/issues/1323) · [#3564](https://github.com/xtermjs/xterm.js/issues/3564)
- VSCode: [`terminalInstance.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/terminal/browser/terminalInstance.ts) · [`terminalTabbedView.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/terminal/browser/terminalTabbedView.ts) · [`xtermTerminal.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/terminal/browser/xterm/xtermTerminal.ts)
- [Warp · How Warp Works](https://www.warp.dev/blog/how-warp-works) (nativo, no Tauri)
- [Windows Terminal · panes spec](https://github.com/microsoft/terminal/blob/main/doc/specs/%23532%20-%20Panes%20and%20Split%20Windows.md)
- [Wave Terminal · Block System](https://deepwiki.com/wavetermdev/waveterm/3.2-block-system) (Electron, no Tauri)

**Single source of truth:**
- [Zustand](https://github.com/pmndrs/zustand) · [TkDodo · Working with Zustand](https://tkdodo.eu/blog/working-with-zustand)
- [TanStack Query · Optimistic Updates](https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates)
- [React · useSyncExternalStore](https://react.dev/reference/react/useSyncExternalStore)
- [Excalidraw discussion #8121](https://github.com/excalidraw/excalidraw/discussions/8121)
- [Reverse engineering Linear · Pustelto](https://pustelto.com/blog/reverse-engineer-linear-1-header/)

**Tauri v2 Mac:**
- [Store plugin](https://v2.tauri.app/plugin/store/) · [Window State plugin](https://v2.tauri.app/plugin/window-state/) · [Menu API](https://v2.tauri.app/learn/window-menu/)
- [Tauri #4783 · window.prompt](https://github.com/tauri-apps/tauri/issues/4783) · [#12576 · alert/confirm async](https://github.com/tauri-apps/tauri/issues/12576)
- [Tauri #2827 · backdrop transparent](https://github.com/tauri-apps/tauri/issues/2827) · [#6876 · backdrop-filter on move](https://github.com/tauri-apps/tauri/issues/6876) · [#13415 · DMG transparency](https://github.com/tauri-apps/tauri/issues/13415)
- [Tauri #4309 · rubber banding](https://github.com/tauri-apps/tauri/issues/4309) · [wry #557](https://github.com/tauri-apps/wry/issues/557)
- [Tauri #5500 · prevent_exit loop](https://github.com/tauri-apps/tauri/issues/5500) · [#9198 · ExitRequested macOS](https://github.com/tauri-apps/tauri/issues/9198)
- [Cursedfunction · Persisting Window State on macOS](https://cursedfunction.io/blog/persisting-tauri-window-state/)
- [Spacedrive](https://github.com/spacedriveapp/spacedrive) · [Reor](https://github.com/reorproject/reor) (referentes Tauri v2)
