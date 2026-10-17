import type { AgentMessage } from '@sandwalk/agent-ui-core'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ChatTranscriptMessageEntry } from './chat-transcript-message-entry'
import type { TranscriptEntry } from './transcript'

function userEntry(content: string): Extract<TranscriptEntry, { kind: 'message' }> {
  const message: AgentMessage = {
    id: 'm1',
    sessionId: 's1',
    role: 'user',
    content,
    source: null,
    createdAt: '2026-10-16T19:49:00Z'
  } as AgentMessage
  return { kind: 'message', message, content } as Extract<TranscriptEntry, { kind: 'message' }>
}

function renderEntry(
  content: string,
  overrides: Partial<Parameters<typeof ChatTranscriptMessageEntry>[0]> = {}
) {
  return render(
    <ChatTranscriptMessageEntry
      entry={userEntry(content)}
      runActive={false}
      runIdByMessageId={{}}
      usageByRunId={{}}
      lastMessageId="m1"
      copiedMessageId={null}
      setCopiedMessageId={() => {}}
      session={null}
      onOpenFile={() => {}}
      {...overrides}
    />
  )
}

describe('ChatTranscriptMessageEntry edit & resend', () => {
  afterEach(() => cleanup())

  it('hides the edit action when no resend handler is wired', () => {
    renderEntry('hi')
    expect(screen.queryByRole('button', { name: /edit and resend/i })).toBeNull()
  })

  it('opens an inline editor and sends the edited text as a new message', () => {
    const onResendMessage = vi.fn()
    renderEntry('hi', { onResendMessage })
    fireEvent.click(screen.getByRole('button', { name: /edit and resend/i }))
    const editor = screen.getByRole('textbox', { name: /edit message/i }) as HTMLTextAreaElement
    expect(editor.value).toBe('hi')
    fireEvent.change(editor, { target: { value: 'hi there, run it again' } })
    fireEvent.click(screen.getByRole('button', { name: /^send$/i }))
    expect(onResendMessage).toHaveBeenCalledWith('hi there, run it again')
    // Editor closes; the original bubble is back.
    expect(screen.queryByTestId('user-message-editor')).toBeNull()
    expect(screen.getByText('hi')).toBeTruthy()
  })

  it('labels the button Stop & send while a run is active', () => {
    renderEntry('hi', { onResendMessage: vi.fn(), runActive: true })
    fireEvent.click(screen.getByRole('button', { name: /edit and resend/i }))
    expect(screen.getByRole('button', { name: /stop & send/i })).toBeTruthy()
  })

  it('cancel and Escape restore the original without sending', () => {
    const onResendMessage = vi.fn()
    renderEntry('hi', { onResendMessage })
    fireEvent.click(screen.getByRole('button', { name: /edit and resend/i }))
    const editor = screen.getByRole('textbox', { name: /edit message/i })
    fireEvent.change(editor, { target: { value: 'changed' } })
    fireEvent.keyDown(editor, { key: 'Escape' })
    expect(onResendMessage).not.toHaveBeenCalled()
    expect(screen.queryByTestId('user-message-editor')).toBeNull()
    // Reopen: draft reset to the original.
    fireEvent.click(screen.getByRole('button', { name: /edit and resend/i }))
    expect((screen.getByRole('textbox', { name: /edit message/i }) as HTMLTextAreaElement).value).toBe('hi')
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onResendMessage).not.toHaveBeenCalled()
  })

  it('does not send an empty edit', () => {
    const onResendMessage = vi.fn()
    renderEntry('hi', { onResendMessage })
    fireEvent.click(screen.getByRole('button', { name: /edit and resend/i }))
    fireEvent.change(screen.getByRole('textbox', { name: /edit message/i }), { target: { value: '   ' } })
    const send = screen.getByRole('button', { name: /^send$/i }) as HTMLButtonElement
    expect(send.disabled).toBe(true)
  })
})
