import type { LocalAgentClient } from '@sandwalk/agent-local-client'
import type { AgentSession } from '@sandwalk/agent-ui-core'
import { useMemo, useState } from 'react'

import { ChatTranscript } from '@/components/agents/ChatTranscript'
import { buildConversationTimeline } from '@/components/agents/transcript'
import { useChatScroll } from '@/hooks/useChatScroll'
import type { SessionChatState } from '@/lib/sessions'

export function CapyChat({
  client,
  session,
  chat,
  chats = [],
  onChatChange,
  onStop
}: {
  client: LocalAgentClient
  session: AgentSession | null
  chat: SessionChatState
  chats?: AgentSession[]
  onChatChange: (
    value: SessionChatState | ((prev: SessionChatState) => SessionChatState)
  ) => void
  onStop: () => void
}) {
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null)

  const conversationTimeline = useMemo(
    () =>
      buildConversationTimeline({
        messages: chat.messages,
        tools: chat.tools,
        todosByRunId: chat.todosByRunId,
        plansByRunId: chat.plansByRunId,
        runIdByMessageId: chat.runIdByMessageId,
        activeRunId: chat.activeRunId
      }),
    [
      chat.activeRunId,
      chat.messages,
      chat.plansByRunId,
      chat.runIdByMessageId,
      chat.todosByRunId,
      chat.tools
    ]
  )

  const activeRunTools = useMemo(
    () =>
      chat.tools.filter(
        tool => chat.activeRunId && tool.runId === chat.activeRunId
      ),
    [chat.activeRunId, chat.tools]
  )

  const scroll = useChatScroll({
    sessionId: session?.id ?? 'capy',
    messagesLoaded: chat.messagesLoaded,
    messagesLength: chat.messages.length,
    conversationTimelineLength: conversationTimeline.length
  })

  return (
    <ChatTranscript
      chatScrollRef={scroll.chatScrollRef}
      chatEndRef={scroll.chatEndRef}
      conversationTimeline={conversationTimeline}
      expandedToolRunKeys={chat.expandedToolRunKeys}
      sessionId={session?.id ?? null}
      client={client}
      onToggleToolRunExpanded={key =>
        onChatChange(prev => ({
          ...prev,
          expandedToolRunKeys: {
            ...prev.expandedToolRunKeys,
            [key]: !prev.expandedToolRunKeys[key]
          }
        }))
      }
      runActive={chat.runActive}
      tools={chat.tools}
      runIdByMessageId={chat.runIdByMessageId}
      usageByRunId={chat.usageByRunId}
      messages={chat.messages}
      copiedMessageId={copiedMessageId}
      setCopiedMessageId={setCopiedMessageId}
      session={session}
      onOpenFile={() => undefined}
      onInterrupt={onStop}
      activeRunTools={activeRunTools}
      activeRunTodos={
        chat.activeRunId ? chat.todosByRunId[chat.activeRunId] || [] : []
      }
      liveDelta={chat.liveDelta}
      showScrollToBottom={scroll.showScrollToBottom}
      onScrollToBottom={scroll.scrollChatToBottom}
      mentionChats={chats}
    />
  )
}
