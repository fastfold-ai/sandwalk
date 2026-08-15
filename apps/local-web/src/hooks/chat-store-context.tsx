import {
  createContext,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState
} from 'react'

import {
  applyChatPatch,
  normalizeSessionChatState
} from '@/lib/chat-actions'
import { emptySessionChatState, type SessionChatState } from '@/lib/sessions'

/**
 * Store global del chat por sesión. Vive una sola vez en el shell (App.tsx)
 * y lo consumen todos los mounts vía `useChatStore` — importante para split
 * view: sin este store compartido, cada `SessionChatMount` tenía su propio
 * `useState({})` local y no veía el historial cargado por otros mounts (ni
 * podía compartir el stream SSE que llegara al chat activo del shell).
 *
 * La API es la misma que exponía `useSessionChatState` antes del refactor
 * (chatBySessionId + setter + ref sincronizado + patchChat), así los hooks
 * downstream (`useSessionChatStream`, `useSessionActions`, etc.) siguen
 * recibiendo los mismos parámetros — solo cambia el origen: en vez de un
 * `useState` local pasan a leer del context.
 */

type ChatStore = {
  chatBySessionId: Record<string, SessionChatState>
  setChatBySessionId: Dispatch<
    SetStateAction<Record<string, SessionChatState>>
  >
  chatBySessionIdRef: React.MutableRefObject<
    Record<string, SessionChatState>
  >
  patchChat: (
    id: string,
    patch:
      | Partial<SessionChatState>
      | ((prev: SessionChatState) => SessionChatState)
  ) => void
  /**
   * Snapshot normalizado del chat de un session id. Usado por selectors
   * downstream (session-scoped hooks) para no rehacer la normalización en
   * cada lugar que lo consume.
   */
  selectChat: (sessionId: string | null) => SessionChatState
}

const ChatStoreContext = createContext<ChatStore | null>(null)

export function ChatStoreProvider({ children }: { children: ReactNode }) {
  const [chatBySessionId, setChatBySessionId] = useState<
    Record<string, SessionChatState>
  >({})

  const chatBySessionIdRef = useRef(chatBySessionId)
  chatBySessionIdRef.current = chatBySessionId

  const patchChat = useCallback<ChatStore['patchChat']>(
    (id, patch) => {
      setChatBySessionId(current => {
        const prev = current[id] ?? emptySessionChatState()
        const next = applyChatPatch(prev, patch)
        if (next === prev) return current
        return { ...current, [id]: next }
      })
    },
    []
  )

  const value = useMemo<ChatStore>(
    () => ({
      chatBySessionId,
      setChatBySessionId,
      chatBySessionIdRef,
      patchChat,
      selectChat: (sessionId: string | null) =>
        normalizeSessionChatState(
          sessionId
            ? chatBySessionId[sessionId] ?? emptySessionChatState()
            : emptySessionChatState()
        )
    }),
    [chatBySessionId, patchChat]
  )

  return (
    <ChatStoreContext.Provider value={value}>
      {children}
    </ChatStoreContext.Provider>
  )
}

export function useChatStore(): ChatStore {
  const store = useContext(ChatStoreContext)
  if (!store) {
    throw new Error(
      'useChatStore must be used within <ChatStoreProvider>. Wrap the app root.'
    )
  }
  return store
}
