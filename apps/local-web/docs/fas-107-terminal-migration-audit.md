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

## 8 · Persistencia y solidez del terminal (segundo bloque de trabajo)

Después de aplicar X3 (barrido cross-superficie), el usuario reportó cuatro síntomas nuevos que están fuera del alcance del barrido y forman un bloque de trabajo aparte. Este bloque se divide en **dos capas** independientes que se pueden ejecutar por separado.

### 8.1 · Síntomas reportados

1. **Buffer del terminal desaparece al navegar entre tabs.** El "cuaderno" del xterm (comandos + output visibles) se pierde cuando el usuario cambia de tab. Al volver, el terminal aparece vacío.
2. **El rename del terminal no se refleja de inmediato.** Después de renombrar, el título viejo persiste hasta que el `refresh()` del backend completa.
3. **El botón X del chip del terminal en el strip no cierra el terminal.** Reportado en runtime, no reproducido todavía en dev.
4. **Después de un rato largo, el buffer se muestra "cortado".** Solo se ve un trozo del output, la vista queda truncada de forma inesperada.

### 8.2 · Causas raíz identificadas

**Síntoma 1 (buffer desaparece):**
El `useEffect` del `TerminalPortalHost` (`terminal-layer/TerminalPortalHost.tsx:148`) depende de `[hostNode]`. Su cleanup llama `term.dispose()`. Cuando el `hostNode` cambia (por re-render del portal, cambio transitorio de `layerRoot` a null, o remount del div), el cleanup destruye el xterm y el buffer se pierde.

Patrón confirmado en el research (§4.1): VSCode usa `Terminal.open()` una sola vez y luego `newContainer.appendChild(term.element)` para mover el buffer sin destruir. Nuestro código actual dispose+recrea.

**Síntoma 2 (rename lento):**
`handleRenameTerminal` (`App.tsx`) hace `await client.updateTerminal(...)` seguido de `refresh()`. Ambos son round-trips al backend. No hay patch optimista al store singleton, así que el UI muestra el nombre viejo durante ~400ms.

**Síntoma 3 (X del tab):**
Cadena de props verificada correcta. Requiere reproducción en runtime para confirmar el fallo.

**Síntoma 4 (buffer cortado):**
Sospecha: `fit.proposeDimensions()` devuelve un tamaño degenerado en algún tick, o el `ResizeObserver` recibe un rect con dimensiones inválidas y el reflow trunca el buffer. Requiere reproducción con condiciones específicas (rato largo, background/foreground, resize).

### 8.3 · Capa 1 · Funcionamiento básico "mientras la app está abierta"

Cubre los síntomas 1, 2 y parte del 4. El norte es: **mientras Sandwalk esté abierto (foreground o background), el terminal se comporta como Warp — navegar, minimizar, cambiar de app y volver funciona sin perder nada.**

**Fix 1 · No destruir el xterm al navegar.**
Separar el `useEffect` del `TerminalPortalHost` en dos:
- Uno con deps `[]` que crea el xterm + WebSocket una sola vez y solo hace `dispose()` cuando el componente se desmonta de verdad (el terminal fue eliminado del store).
- Otro con deps `[hostNode]` que hace `term.open(hostNode)` la primera vez y `newHost.appendChild(term.element)` las siguientes. Patrón VSCode `_attached`.

**Fix 2 · Rename optimista.**
Después del `await client.updateTerminal(...)`, llamar `patchTerminal(id, { title })` al store. El UI se actualiza sin esperar al refresh.

**Fix 3 · Reconexión automática de la conexión backend↔frontend.**
El WebSocket local puede caerse por timeout después de mucho tiempo con la app en background. Detectar `ws.onclose` y reintentar cada 2 segundos con backoff. Al reconectar, seguir escribiendo al mismo xterm (buffer preservado).

**Fix 4 · Detectar visibility change.**
Cuando Sandwalk vuelve del background (Page Visibility API `document.visibilitychange` → visible), verificar que el WebSocket esté conectado. Si no lo está, forzar reconexión.

**Fix 5 · Sanidad del `fit.proposeDimensions()`.**
Cuando devuelve un tamaño con `cols < 10` o `rows < 3`, no propagar al PTY. Esperar al siguiente frame. Log para diagnóstico si persiste. Cubre el síntoma 4 parcialmente.

**Fix 6 · Diagnóstico del síntoma 3.**
Agregar un log temporal en el chip X del strip y en `handleDeleteTerminalGlobal` para confirmar si el handler dispara. Si dispara pero no borra, es un bug del optimistic remove; si no dispara, es la cadena de props.

**Alcance:** este es el bloque que arregla los bugs que hoy molestan a diario. Debe ir primero.

### 8.4 · Capa 2 · Persistir al cerrar y reabrir (paridad con Warp)

Cubre el caso "cerrar Sandwalk con Cmd+Q y reabrir mantiene el output visible de los terminales".

**Investigación clave (§8.5):** Warp NO mantiene los procesos vivos al cerrar. Los shells mueren. Antes de cerrar, Warp guarda el "cuaderno" (buffer serializado) a disco en SQLite. Al reabrir, dibuja el cuaderno en un xterm nuevo con un shell nuevo. Es "serialize-and-replay", no un daemon vivo.

VSCode hace lo mismo con `terminal.integrated.enablePersistentSessions` (feature "Process Revive"). Único approach que sí mantiene procesos vivos es tmux o Wave Terminal (daemon separado del GUI). Ambos requieren rediseño mayor.

**Plan para Sandwalk (equivalente Warp):**

**Paso 1 · Al cerrar Sandwalk (`RunEvent::ExitRequested` en Rust)**, antes de matar el backend Python:
- Para cada terminal activo, serializar el buffer del xterm con `SerializeAddon` de xterm.js.
- Guardar cada snapshot en disco (JSON o binario) en `~/Library/Application Support/<bundle-id>/terminals/<terminalId>.snapshot`.
- Registrar cwd, env vars conocidos (opt-in) y último comando (opcional, para posible "replay" futuro).

**Paso 2 · Al reabrir Sandwalk:**
- Cuando el `TerminalPortalHost` monta el xterm para un `terminalId` que tiene snapshot, leer el archivo y hacer `term.write(snapshotString)` antes de conectar el WebSocket.
- El PTY arranca nuevo, vacío, listo para el próximo comando. El buffer viejo se ve intacto.

**Trade-offs:**
- Pro: paridad visual con Warp. El usuario no siente que "perdió" nada al cerrar.
- Contra: los comandos long-running (`npm start`, `docker run`) no siguen corriendo. Igual que Warp.
- Costo: espacio en disco por terminal (unos MB con `scrollback: 5000`).
- Complejidad principal: coreografía del `ExitRequested` (guardar antes de matar).

**Alcance:** este bloque toca backend Python + integración Tauri Rust. Es un PR aparte. **NO se planifica todavía.** Se retoma cuando Capa 1 esté cerrada y el usuario confirme que el funcionamiento básico está sólido.

### 8.5 · Referentes de persistencia terminal (research)

| App | Restaura output al reabrir | Mantiene procesos vivos | Cómo lo hace |
|---|---|---|---|
| **Warp** | Sí (automático) | No | SQLite en disco, dibuja snapshot al reabrir con shell nuevo |
| **iTerm2** | Sí (opt-in) | No | Buffer a disco en clean quit. Con integración tmux sí mantiene procesos |
| **VSCode** | Sí (`enablePersistentSessions`) | No (Process Revive) | Serializa buffer + relanza shell |
| **Hyper** | No built-in | No | Feature request abierta desde 2018 |
| **Wave Terminal** | Sí | Sí | Go backend como daemon separado del Electron |
| **Zed** | No | No | RFC abierto, workaround = tmux |

**Conclusión:** el único approach que mantiene procesos vivos requiere un daemon separado del GUI. En Sandwalk hoy el backend Python vive dentro del proceso Tauri; Cmd+Q los mata a los dos. Cambiar eso implicaría rediseñar el ciclo de vida de la app (instalador, updater, macOS Login Items). Es un proyecto propio, fuera de este documento.

El approach factible es el de Warp/VSCode: serialize-and-replay. Cubre el 80% del beneficio percibido con esfuerzo bajo-medio.

---

## 9 · X4 · Replanteo arquitectónico (rediseño profesional)

Después de intentar aplicar la Capa 1 con parches puntuales, se identificó un **bug arquitectónico en la Fase 1 del X3** que obliga a replantear el enfoque. La documentación previa (§8.3) queda superada por este §9.

### 9.1 · Bug arquitectónico identificado

En `lib/terminals-store.ts` (creado en X3 Fase 1) el snapshot devuelve siempre la misma referencia porque el objeto se muta en el sitio:

```
export function getTerminalsSnapshot(): TerminalsState {
  return state   // ← misma referencia aunque state.terminals cambie
}
```

React `useSyncExternalStore` compara referencias con `Object.is`. Al ser siempre la misma, **React no re-renderea hasta que otra cosa lo obliga** (ejemplo: cambio de tab). Explica directamente el síntoma reportado del "X del chip no cierra inmediato pero al cambiar de tab sí".

Es un bug de implementación del store manual, no un parche menor. La solución correcta es reemplazar el patrón por una librería probada que garantice re-render por diseño.

### 9.2 · Diagnóstico honesto de X3

Fase 1 del X3 fue una implementación mediocre: evitar Zustand "para ahorrar dependencia" fue un atajo que introdujo el bug crítico anterior. El resto del X3 (Fases 2, 3, 4, 5, 6a, 7) sigue siendo válido y no se toca.

### 9.3 · Estrategias de rediseño

Cuatro estrategias, ordenadas de más fundacional a más superficial. Cada una habilita la siguiente.

**Estrategia 1 · Store con Zustand**
Reemplazar `terminals-store.ts` manual por un store Zustand. Elimina el bug de la referencia por diseño; cada action genera un objeto nuevo, los suscriptores se enteran garantizado. Selectores atómicos por componente.
- Toca solo `lib/terminals-store.ts` y `useAppTerminals.ts`.
- Habilitante para todo lo demás.

**Estrategia 2 · Componente `<TerminalSession>` que engloba el ciclo completo**
Hoy el ciclo del terminal está fragmentado en 5+ archivos y 6 handlers (`TerminalHostsProvider`, `TerminalPortalHost`, `TerminalPlaceholder`, `TerminalLeaf`, `TerminalSplitPanelHeader`, `AgentSessionMainPanel`, `App.tsx`). Cada superficie (strip, sidebar, split, ruta directa) monta y desmonta piezas distintas. La convivencia falla por diseño.

Rediseño:
- Un solo `<TerminalSession terminalId={id}>` que engloba el ciclo completo: crear, conectar WebSocket, dibujar, reconectar si se cae, dispose solo cuando el terminal se elimina de verdad.
- Envoltorios (`<TerminalStrip>`, `<TerminalSidebar>`, `<TerminalInSplit>`) solo posicionan y decoran. No tocan el ciclo de vida.
- Hook `useTerminalActions()` único que expone `{ rename, delete, moveToProject, togglePin, close }`. Cero prop drilling.

**Estrategia 3 · Command bus para acciones (en observación)**
Alternativa a props: los menús emiten `terminal.close(id)`, el sistema los ejecuta. Menos props, menos races. Riesgo: paradigma nuevo. Se evalúa después de Estrategia 2; si `useTerminalActions()` limpia el drilling, no hace falta.

**Estrategia 4 · Tests como red de seguridad**
Antes de mover una línea de Estrategia 2:
- Unit tests del store (crear, borrar, patch, optimistic).
- Component tests de `<TerminalSession>` con WebSocket mockeado.
- E2E con Playwright para flujos strip/sidebar/split/ruta directa.

Sin tests, cualquier rediseño arriesga regresiones. Son prerequisito, no complemento.

### 9.4 · Plan de trabajo X4

| Fase | Qué | Tiempo estimado | Habilita |
|---|---|---|---|
| **X4.0** | Estrategia 1: migrar store a Zustand | ~1 hora | Todo lo demás |
| **X4.1** | Estrategia 4: setup Playwright + tests base del terminal | ~1 día | X4.2 sin regresiones |
| **X4.2** | Estrategia 2: `<TerminalSession>` monolítico + `useTerminalActions()` | ~2-3 días | Convivencia sólida |
| **X4.3** | Aplicar los 6 fixes de Capa 1 sobre la nueva arquitectura | ~1 día | Comportamiento tipo Warp |
| **X4.4** (futuro) | Capa 2: persistir buffer al cerrar/reabrir | ~2 días | Paridad Warp completa |

Estrategia 3 pendiente de evaluación después de X4.2.

### 9.5 · Validación: los 6 fixes de Capa 1 sobre X4.2

Al terminar X4.2, los 6 fixes se aplican sobre la nueva arquitectura:

| Fix | Cómo se aplica sobre `<TerminalSession>` |
|---|---|
| 1 · No destruir xterm al navegar | El componente `<TerminalSession>` monta xterm una vez, expone `attachToElement(node)` para moverlo entre placeholders. Dispose solo en unmount real. Patrón VSCode `_attached` embebido |
| 2 · Rename optimista | Zustand action `patchTerminal(id, {title})` emite nuevo snapshot; todos los suscriptores actualizan sin refresh |
| 3 · Reconexión automática WS | El componente maneja `ws.onclose` con backoff exponencial. Estado interno `connected: boolean` expuesto |
| 4 · Detectar visibility change | `useEffect` interno con `document.visibilitychange`. Al volver a visible, verifica WS y reconecta |
| 5 · Sanidad de `fit.proposeDimensions` | Guard interno: si `cols < 10 || rows < 3`, se pospone al siguiente frame |
| 6 · X del chip que no cierra | Resuelto by design por Estrategia 1 (Zustand): `removeTerminal(id)` emite snapshot nuevo, el chip re-renderea inmediato |

Por diseño, cada fix es una responsabilidad interna del `<TerminalSession>` en vez de código dispersado por 5 archivos.

### 9.6 · Conclusiones del research consolidado

Dos investigaciones paralelas contra fuentes reales (VSCode, Warp, Wave Terminal, Hyper, Tabby, Windows Terminal, xterm.js, Tauri v2 docs, apps Tauri productivas) validan y refinan el plan.

#### 9.6.1 · Arquitectura del `<TerminalSession>` — tres capas explícitas

Consenso de VSCode `TerminalInstance`, Wave `ViewModel`, Tabby `BaseTerminalTabComponent` y Windows Terminal `ControlCore/Interactivity/Control` (PR #9820):

- **`TerminalCore`** (sin React): dueño del WebSocket, PTY, instancia `xterm.Terminal`, `SerializeAddon`. Métodos: `attachToElement(el)`, `detach()`, `dispose()`, `focus()`, `resize(cols, rows)`, `sendData(s)`, `write(bytes)`. Eventos: `onData`, `onExit`, `onTitleChange`, `onDimensionsChanged`, `onConnectionState`.
- **`TerminalInteractivity`**: keybinds, focus, `ResizeObserver`, selection.
- **`TerminalView`** (componente React puro): renderea el placeholder, llama `attachToElement(ref)` cuando el ref cambia, expone estado visual (active/inactive/loading/error).

La instancia `TerminalCore` vive **fuera del árbol React**, en un `TerminalService` global keyed by `terminalId`. React monta y desmonta `TerminalView`; la sesión sobrevive.

#### 9.6.2 · Multi-surface: `react-reverse-portal`

Un solo `<InPortal>` por terminal montado una vez al top del árbol de `AppShellMain`. Cada surface (strip, sidebar, split, ruta `/terminals/:id`) pinta `<OutPortal node={portalNodes[id]} />`. Solo una surface renderea el terminal por vez — regla explícita del sistema, no accidente.

Esto reemplaza el `TerminalPortalHost` + `TerminalPlaceholder` + `TerminalHostsProvider` actual con un único componente. Menos code, menos races.

#### 9.6.3 · Command hub, no event bus

VSCode usa `ITerminalService` como command hub inyectado, no pub/sub abstracto. En React 2026 el equivalente es un **Zustand store con acciones tipadas** (`terminalService.close(id)`, `.rename(id, name)`, etc). Los menús llaman al servicio directamente. Cero event bus.

**Estrategia 3 (command bus) descartada oficialmente.** Se reemplaza por acciones del store.

#### 9.6.4 · Stack de state (Tauri v2 confirmado)

- **Zustand v5** con selectores atómicos. Sin `useShallow` para selectores simples (una prop a la vez). `subscribeWithSelector` solo para stream del PTY (imperativo, fuera de React).
- **`persist` middleware** para preferencias UI puras (tamaño de fuente, tema del terminal).
- **`@tauri-store/zustand`** para state que el backend Python DEBE leer. No hay caso claro hoy en el terminal.
- **Sin TanStack Query** en el terminal. Válido para invocaciones costosas del backend (listados grandes) fuera del scope de terminales.
- **Sin Redux DevTools middleware**: WKWebView no soporta extensiones. Alternativa: panel dev custom o `redux-logger`.

#### 9.6.5 · Reconexión WebSocket — patrón `replay-then-connect`

Confirmado por VSCode y xterm.js community:

1. Server mantiene el PTY vivo.
2. Cliente reconecta al WebSocket.
3. Server envía snapshot del buffer (`SerializeAddon.serialize()`).
4. Cliente hace `terminal.write(snapshot)`.
5. **Después** engancha el stream vivo.

Backoff: `min(500ms * 2^n + jitter, 30s)`, cap 12 intentos. Heartbeat cada 25s, 3 pongs perdidos → reconectar. **Obligatorio** porque WKWebView cierra WebSockets silenciosamente al pasar a background (Apple forum #716118).

#### 9.6.6 · Background/foreground

`document.visibilitychange` con:
- `hidden`: NO cerrar el WS (backend local, no vale la pena). Solo pausar timers de UI puros.
- `visible`: forzar ping inmediato. Si no hay pong en 3s, reconectar.

En Sandwalk el backend Python vive dentro del proceso Tauri, así que la única causa real de reconexión es HMR del frontend en dev o crash puntual del WS. El PTY sobrevive mientras el proceso Tauri viva.

#### 9.6.7 · Testing stack

- **Vitest + React Testing Library** (copiar setup de [`dannysmith/tauri-template`](https://github.com/dannysmith/tauri-template)). `environment: 'jsdom'`, mock de `@tauri-apps/api/core`.
- **`vitest-websocket-mock`** para tests del `TerminalCore` con WS.
- **`@xterm/headless`** para tests del parser/buffer sin DOM.
- **E2E**: `@wdio/tauri-service` con provider embedded (`tauri-plugin-wdio-webdriver`) es la vía oficial en docs Tauri v2. **Playwright estándar NO funciona en Tauri Mac** (WKWebView no expone CDP). Alternativa: `srsholmes/tauri-playwright` menos maduro.

Recomendación: unit + component con Vitest cubren el 80%. E2E se difiere hasta que un caso lo pida.

#### 9.6.8 · Migración: Strangler Fig con feature flag

`useTerminalStore.getState().useNewImplementation` como flag. Un hook fachada elige entre el store viejo (X3 Fase 1) y el nuevo (X4.0 Zustand). Ambos corren en paralelo hasta que el nuevo pase todos los tests. Rollback instantáneo por flag. Patrón consolidado en Excalidraw y VSCode migrations.

### 9.7 · Validación contra los 9 síntomas reportados

| # | Síntoma | Cubierto en X4 por... | Estado |
|---|---|---|---|
| A | Menús contextuales no salen (strip + sidebar) | X3 Fase 5 (ya aplicada) | Cubierto |
| B | Terminal no aparece, espacio negro vacío | X4.0 (Zustand snapshot inmutable) + X4.2 (`<TerminalSession>` con `TerminalService` global) | **Resuelto por diseño** |
| C | Terminal aparece mal, sin solidez visual | X4.2 (`TerminalCore` + `attachToElement`) + X4.3 (heartbeat + guards de fit) | Cubierto |
| D | Chip "Hi" no cierra ni abre | X3 Fase 4 (ya aplicada) | Cubierto |
| E | Buffer del terminal desaparece al navegar | X4.2 (react-reverse-portal + `dispose()` solo en delete real) | **Resuelto por diseño** |
| F | Rename no actualiza inmediato | X4.0 (Zustand action emite snapshot nuevo) | **Resuelto por diseño** |
| G | X del chip no cierra inmediato | X4.0 (Zustand snapshot inmutable) | **Resuelto por diseño** |
| H | Buffer cortado después de rato largo | X4.3 (guard de fit + heartbeat) | Cubierto |
| I | Errores al cargar terminal | X4.2 (`TerminalCore` con replay-then-connect + backoff) | Cubierto — requiere repro para logs específicos |

**4 síntomas se resuelven por diseño arquitectónico** (B, E, F, G) — no como parches, sino porque la arquitectura correcta los hace imposibles. **5 se cubren activamente** con fixes que ya son responsabilidad interna del `<TerminalSession>`.

### 9.8 · Plan de trabajo actualizado

| Fase | Qué | Tiempo estimado | Habilita |
|---|---|---|---|
| **X4.0** | Zustand store singleton con selectores atómicos. Migrar `useAppTerminals` como fachada del store nuevo. Flag `useNewImplementation` para strangler fig | ~2 horas | Todo lo demás |
| **X4.1** | Setup Vitest + RTL + `vitest-websocket-mock` + `@xterm/headless`. Copiar setup de `dannysmith/tauri-template`. Tests base del store (crear, borrar, patch, optimistic) | ~1 día | X4.2 sin regresiones |
| **X4.2** | `TerminalCore` (tres capas), `TerminalService` con acciones, `<TerminalSession>` con `attachToElement`. Multi-surface con `react-reverse-portal`. `useTerminalActions()` | ~2-3 días | Convivencia sólida |
| **X4.2b** | `useGroupActions()` como hook único de acciones de grupos. Refactor menús del strip y sidebar para consumirlo. Cierra las 3 asimetrías §3.2 por diseño | ~1 día | Simetría chat/terminal/grupo |
| **X4.3** | Aplicar los 6 fixes de Capa 1 (replay-then-connect, heartbeat, visibility, guards de fit) como responsabilidades del `TerminalCore` | ~1 día | Comportamiento tipo Warp |
| **X4.4** (futuro) | Persistir buffer al cerrar/reabrir (Capa 2) usando `SerializeAddon` + `RunEvent::ExitRequested` en Rust | ~2 días | Paridad Warp completa |

**Referente arquitectónico principal a copiar:** Wave Terminal block system (`ViewModel` reactivo por bloque + `globalStore`), sustituyendo Jotai por Zustand. Adaptación 1:1 al patrón de tres capas de VSCode/Windows Terminal.

### 9.9 · X4.2b · `useGroupActions()` — análisis y diseño

Las 3 asimetrías detectadas en §3.2 comparten la **misma causa raíz que motivó el X4** para terminales: prop drilling largo desde `App.tsx` hasta los menús + handlers dispersos + asimetría entre superficies porque cada una recibe una selección distinta de props.

La solución arquitectónica es el paralelo de `useTerminalActions()`: un hook único `useGroupActions()` que expone todas las acciones del grupo consumibles desde cualquier superficie sin drilling.

**Acciones del grupo (`useAppTabGroups` ya las tiene, solo falta unificar la fachada):**

| Acción | Store | Conectada strip | Conectada sidebar | Post X4.2b |
|---|---|---|---|---|
| `rename(id, name)` | ✓ | ✓ | ✓ | ✓ |
| `setColor(id, color)` | ✓ | ✓ | ✓ | ✓ |
| `setPinned(id, pinned)` | ✓ | **✗** | **✗** | ✓ |
| `dissolve(id)` | ✓ | ✓ | ✓ | ✓ |
| `closeTab(id)` | ✓ | ✓ | **✗** | ✓ |
| `moveToProject(id, projectId)` | (add) | ✗ | ✗ | ✓ |

**Beneficios secundarios:**
- Futuras acciones (`archive`, `duplicate`) aparecen en todas las superficies sin drilling.
- Tests del store cubren las acciones. Los menús solo testean "click dispara acción" (component test simple).
- Un solo lugar canónico donde documentar "qué se puede hacer con un grupo".

**Validación de simetría (chat + terminal + grupo con el mismo patrón):**

| Item | Hook | Acciones expuestas |
|---|---|---|
| Chat | `useChatActions()` (existe parcial) | rename, delete, move, pin, archive, color |
| Terminal | `useTerminalActions()` (X4.2) | rename, delete, moveToProject, pin, archive, color, close, removeFromSplit |
| Grupo | `useGroupActions()` (X4.2b) | rename, setColor, setPinned, dissolve, closeTab, moveToProject |

Con esta anexión el sistema queda simétrico entre los tres tipos de items. La convivencia se resuelve por arquitectura, no por parches puntuales.

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

**Persistencia terminal (Capa 2, futura):**
- [Warp · Session Restoration](https://docs.warp.dev/terminal/sessions/session-restoration/) · [Warp #9416 · keep sessions alive](https://github.com/warpdotdev/warp/issues/9416) · [Warp #10583 · replay on restore](https://github.com/warpdotdev/warp/issues/10583)
- [iTerm2 · Session Restoration](https://iterm2.com/documentation-restoration.html) · [iTerm2 · Why no content](https://iterm2.com/why_no_content.html)
- [VSCode · Terminal Advanced](https://code.visualstudio.com/docs/terminal/advanced) · [João Moreno · Persistent terminal sessions](https://medium.com/@joaomoreno/persistent-terminal-sessions-in-vs-code-8fc469ed6b41)
- [xterm.js SerializeAddon (npm)](https://www.npmjs.com/package/@xterm/addon-serialize) · [source](https://github.com/xtermjs/xterm.js/tree/master/addons/addon-serialize) · [#595 · save/restore state](https://github.com/xtermjs/xterm.js/issues/595)
- [Superset · Persistent Terminal Daemon for Electron](https://superset.sh/blog/terminal-daemon-deep-dive)
- [Wave Terminal · Block System](https://deepwiki.com/wavetermdev/waveterm/3.2-block-system) · [Block Controllers](https://deepwiki.com/wavetermdev/waveterm/7.1-block-controller)
- [Zed RFC #50584 · persistent terminal](https://github.com/zed-industries/zed/discussions/50584)
- [Daniel Cosenza · How terminal multiplexers keep sessions alive](https://danielcosenza.com/posts/sh-terminal-multiplexer-internals/)

**X4 · Rediseño arquitectónico (research 2026):**
- [VSCode · terminalInstance.ts](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/terminal/browser/terminalInstance.ts) · [DeepWiki Terminal](https://deepwiki.com/microsoft/vscode/6-integrated-terminal) · [UI & Layout](https://deepwiki.com/microsoft/vscode/6.6-terminal-ui-and-layout)
- [Windows Terminal · PR #9820 · ControlCore split](https://github.com/microsoft/terminal/pull/9820)
- [Wave Terminal · Block System](https://deepwiki.com/wavetermdev/waveterm/3.2-block-system) · [Block Types & Views](https://deepwiki.com/wavetermdev/waveterm/4-core-functionality)
- [Tabby · baseTerminalTab.component.ts](https://github.com/Eugeny/tabby/blob/43cd3318dac4a47bd31862f9428fe98f07714c59/tabby-terminal/src/api/baseTerminalTab.component.ts) · [Terminal Engine](https://deepwiki.com/Eugeny/tabby/3.1-terminal-engine)
- [react-reverse-portal](https://github.com/httptoolkit/react-reverse-portal) · [DEV article](https://dev.to/pimterry/react-reverse-portals-3jdb)
- [xterm.js reconnect issue #677](https://github.com/xtermjs/xterm.js/issues/677) · [replay discussion #4869](https://github.com/xtermjs/xterm.js/discussions/4869) · [xterm-headless](https://github.com/microsoft/vscode/wiki/Working-with-xterm.js/448aa7d1d72f4bf86074d13e686bdd852f9b4157)
- [Cloudflare PTY replay pattern](https://developers.cloudflare.com/sandbox/concepts/terminal)
- [Zustand + Tauri: @tauri-store/zustand](https://www.npmjs.com/package/@tauri-store/zustand)
- [dannysmith/tauri-template · Vitest setup](https://github.com/dannysmith/tauri-template)
- [Vitest en Tauri (Yonatan Kra)](https://yonatankra.com/how-to-setup-vitest-in-a-tauri-project/)
- [Tauri v2 docs · WebdriverIO](https://v2.tauri.app/develop/tests/webdriver/example/webdriverio/) · [WDIO Tauri platform](https://webdriver.io/docs/desktop-testing/tauri/platform-support/)
- [tauri-playwright (WKWebView native)](https://github.com/srsholmes/tauri-playwright)
- [vitest-websocket-mock](https://www.npmjs.com/package/vitest-websocket-mock)
- [WebSocket reconnection strategies (dev.to)](https://dev.to/hexshift/robust-websocket-reconnection-strategies-in-javascript-with-exponential-backoff-40n1) · [heartbeat guide](https://websocket.org/guides/heartbeat/)
- [WKWebView WS en background (Apple forum #716118)](https://developer.apple.com/forums/thread/716118) · [socket.io #2924](https://github.com/socketio/socket.io/issues/2924)
- [tkdodo · working with Zustand](https://tkdodo.eu/blog/working-with-zustand) · [Zustand selectors DeepWiki](https://deepwiki.com/pmndrs/zustand/2.3-selectors-and-re-rendering)
- [Strangler Fig migration (Steve Kinney)](https://stevekinney.com/courses/enterprise-ui/strangler-fig-introduction)
- [Excalidraw discussion #8121](https://github.com/excalidraw/excalidraw/discussions/8121) · [Linear reverse-engineered](https://github.com/wzhudev/reverse-linear-sync-engine)
