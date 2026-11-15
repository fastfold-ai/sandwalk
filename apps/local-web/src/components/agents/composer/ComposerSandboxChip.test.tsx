import type { SessionSandboxStatus } from '@sandwalk/agent-ui-core'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ComposerSandboxChip } from '@/components/agents/composer/ComposerSandboxChip'
import { ComposerSandboxPicker } from '@/components/agents/composer/ComposerSandboxPicker'
import {
  draftFromSandboxStatus,
  formatSandboxElapsed,
  formatSandboxLimit,
  lifetimeForIdle,
  sandboxBackendName,
  sandboxChipVisible,
  sandboxDraftChangesSettings,
  sandboxIdleChoices,
  sandboxIsLive,
  sandboxLifecycleLine,
  sandboxLifecycleSummary,
  sandboxLifetimeChoices,
  sandboxSpecs,
  sandboxStopLine,
  sandboxStopSummary,
  sandboxTransitionLabel
} from '@/components/agents/composer/sandbox-utils'

function status(overrides: Partial<SessionSandboxStatus>): SessionSandboxStatus {
  return {
    sessionId: 's1',
    backend: 'modal',
    sessionBackend: 'modal',
    globalBackend: 'builtin',
    status: 'running',
    providerSandboxName: null,
    modalConfigured: true,
    computeType: 'gpu',
    gpuClass: 'T4',
    cpuCores: 4,
    ramGb: 16,
    cpuImage: 'python:3.12',
    detail: null,
    ...overrides
  }
}

describe('sandbox chip helpers', () => {
  it('treats a running or transitioning sandbox as live', () => {
    expect(sandboxIsLive(status({}))).toBe(true)
    expect(sandboxIsLive(status({ status: 'starting' }))).toBe(true)
    expect(sandboxIsLive(null, 'stopping')).toBe(true)
  })

  it('does not treat the idle local sandbox or a stopped one as live', () => {
    expect(sandboxIsLive(status({ backend: 'builtin', status: 'ready' }))).toBe(
      false
    )
    expect(sandboxIsLive(status({ status: 'stopped' }))).toBe(false)
    expect(sandboxIsLive(null)).toBe(false)
  })

  it('names the backend and lists GPU, CPU, and RAM', () => {
    expect(sandboxBackendName(status({}))).toBe('Modal')
    expect(sandboxBackendName(status({ backend: 'builtin' }))).toBe('Local')
    expect(sandboxSpecs(status({}))).toBe('T4 GPU · 4 CPU · 16 GB RAM')
    expect(
      sandboxSpecs(status({ computeType: 'cpu', cpuCores: 2, ramGb: 8 }))
    ).toBe('2 CPU · 8 GB RAM')
  })

  it('labels a sandbox that is changing state', () => {
    expect(sandboxTransitionLabel(status({}))).toBeNull()
    expect(sandboxTransitionLabel(status({ status: 'starting' }))).toBe(
      'Starting…'
    )
    expect(sandboxTransitionLabel(status({}), 'stopping')).toBe('Stopping…')
  })

  it('formats elapsed time', () => {
    expect(formatSandboxElapsed(41_000)).toBe('41s')
    expect(formatSandboxElapsed(125_000)).toBe('2m 5s')
    expect(formatSandboxElapsed(3_720_000)).toBe('1h 2m')
  })
})

describe('sandbox lifecycle text', () => {
  const now = Date.parse('2026-11-15T17:10:00Z')
  const running = status({
    startedAt: '2026-11-15T17:00:00Z',
    idleTimeoutSeconds: 600,
    maxLifetimeSeconds: 1800,
    lastActiveAt: '2026-11-15T17:07:00Z',
    expiresAt: '2026-11-15T17:30:00Z'
  })

  it('formats configured limits', () => {
    expect(formatSandboxLimit(600)).toBe('10 min')
    expect(formatSandboxLimit(7200)).toBe('2 h')
    expect(formatSandboxLimit(5400)).toBe('1 h 30 min')
    expect(formatSandboxLimit(45)).toBe('45 s')
  })

  it('says when a running sandbox will stop', () => {
    expect(sandboxLifecycleLine(running, now)).toBe(
      'Stops after 10 min idle (about 7m 0s left) · 30 min limit (20m 0s left)'
    )
  })

  it('does not count idle time down while a command runs', () => {
    expect(sandboxLifecycleLine({ ...running, busy: true }, now)).toBe(
      'Running a command · stops after 10 min idle · 30 min limit (20m 0s left)'
    )
  })

  it('gives no hard-limit countdown for a reattached sandbox', () => {
    expect(sandboxLifecycleLine({ ...running, expiresAt: null }, now)).toBe(
      'Stops after 10 min idle (about 7m 0s left) · 30 min limit'
    )
  })

  it('says the idle stop is due once the estimate runs out', () => {
    expect(
      sandboxLifecycleLine(
        { ...running, lastActiveAt: '2026-11-15T16:59:00Z' },
        now
      )
    ).toContain('(any moment now)')
  })

  it('sums it up as the next stop only', () => {
    // Idle comes first here.
    expect(sandboxLifecycleSummary(running, now)).toBe('Stops in 7 min if idle')
    // The hard limit comes first when it is closer than the idle timeout.
    expect(
      sandboxLifecycleSummary(
        { ...running, expiresAt: '2026-11-15T17:13:00Z' },
        now
      )
    ).toBe('Stops in 3 min')
    // A running command pauses the idle timer; only the limit remains.
    expect(sandboxLifecycleSummary({ ...running, busy: true }, now)).toBe(
      'Stops in 20 min'
    )
    expect(
      sandboxLifecycleSummary(
        { ...running, lastActiveAt: '2026-11-15T16:59:00Z' },
        now
      )
    ).toBe('Stops any moment')
    expect(
      sandboxLifecycleSummary(
        { ...running, lastActiveAt: '2026-11-15T17:09:40Z', expiresAt: null },
        now
      )
    ).toBe('Stops in 10 min if idle')
    expect(
      sandboxLifecycleSummary(
        { ...running, lastActiveAt: '2026-11-15T17:00:20Z' },
        now
      )
    ).toBe('Stops in under a minute if idle')
  })

  it('sums up a stop as how long ago and the cause', () => {
    const stopped = status({
      status: 'stopped',
      stoppedAt: '2026-11-15T17:05:50Z',
      stopReason: 'idle',
      idleTimeoutSeconds: 600
    })
    expect(sandboxStopSummary(stopped, now)).toBe(
      'Stopped 4 min ago · idle timeout'
    )
    expect(
      sandboxStopSummary({ ...stopped, stopReason: 'time_limit' }, now)
    ).toBe('Stopped 4 min ago · time limit')
    expect(sandboxStopSummary({ ...stopped, stopReason: 'ended' }, now)).toBe(
      'Stopped 4 min ago'
    )
  })

  it('says when and why a sandbox stopped', () => {
    const stopped = status({
      status: 'stopped',
      stoppedAt: '2026-11-15T17:05:50Z',
      stopReason: 'idle',
      idleTimeoutSeconds: 600
    })
    expect(sandboxStopLine(stopped, now)).toBe(
      'Stopped 4m 10s ago after 10 min idle'
    )
    expect(
      sandboxStopLine(
        { ...stopped, stopReason: 'time_limit', maxLifetimeSeconds: 1800 },
        now
      )
    ).toBe('Stopped 4m 10s ago at the 30 min limit')
    expect(sandboxStopLine({ ...stopped, stopReason: 'ended' }, now)).toBe(
      'Stopped 4m 10s ago'
    )
    expect(sandboxChipVisible(stopped)).toBe(true)
    // A sandbox the user stopped has no stop note, so nothing lingers.
    expect(sandboxChipVisible(status({ status: 'stopped' }))).toBe(false)
  })
})

describe('sandbox limit settings', () => {
  const HOUR = 3600

  it('starts from the saved limits, or the defaults when none are reported', () => {
    expect(draftFromSandboxStatus(status({}))).toMatchObject({
      idleTimeoutSeconds: 600,
      maxLifetimeSeconds: 1800
    })
    expect(
      draftFromSandboxStatus(
        status({
          configuredIdleTimeoutSeconds: 1800,
          configuredMaxLifetimeSeconds: 8 * HOUR
        })
      )
    ).toMatchObject({ idleTimeoutSeconds: 1800, maxLifetimeSeconds: 8 * HOUR })
  })

  it('offers time limits up to 24 hours, always longer than the idle timeout', () => {
    expect(sandboxLifetimeChoices(1800, 600).map(formatSandboxLimit)).toEqual([
      '30 min',
      '1 h',
      '2 h',
      '4 h',
      '8 h',
      '12 h',
      '24 h'
    ])
    expect(sandboxLifetimeChoices(4 * HOUR, 2 * HOUR)[0]).toBe(4 * HOUR)
    // A value saved elsewhere stays selectable.
    expect(sandboxIdleChoices(900)).toContain(900)
    expect(sandboxLifetimeChoices(5400, 600)).toContain(5400)
  })

  it('moves the time limit up when the idle timeout would outlast it', () => {
    expect(lifetimeForIdle(1800, 600)).toBe(1800)
    expect(lifetimeForIdle(1800, 1800)).toBe(HOUR)
    expect(lifetimeForIdle(HOUR, 4 * HOUR)).toBe(8 * HOUR)
  })

  it('treats a changed limit as something to confirm', () => {
    const saved = status({ cpuCores: 8, ramGb: 32 })
    const draft = draftFromSandboxStatus(saved)
    expect(sandboxDraftChangesSettings(draft, saved)).toBe(false)
    expect(
      sandboxDraftChangesSettings({ ...draft, maxLifetimeSeconds: 4 * HOUR }, saved)
    ).toBe(true)
    expect(
      sandboxDraftChangesSettings({ ...draft, idleTimeoutSeconds: 1800 }, saved)
    ).toBe(true)
  })
})

describe('ComposerSandboxChip', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    cleanup()
    vi.useRealTimers()
  })

  const chip = () => screen.getByRole('button', { name: 'Sandbox' })
  const litCells = () =>
    [...(chip().firstElementChild as HTMLElement).children]
      .map(cell => (cell.className.includes('opacity-0') ? '0' : '1'))
      .join('')

  it('renders nothing for an idle local sandbox', () => {
    const { container } = render(
      <ComposerSandboxChip
        sandboxStatus={status({ backend: 'builtin', status: 'ready' })}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('is a small "1 Sandbox" pill with the dots first, floating over the transcript', () => {
    render(<ComposerSandboxChip sandboxStatus={status({})} />)
    const classes = chip().className.split(/\s+/)
    expect(classes).toContain('rounded-full')
    expect(classes).toContain('w-fit')
    expect(classes).not.toContain('w-full')
    expect(chip().firstElementChild?.children).toHaveLength(9)
    expect(chip().textContent).toBe('1Sandbox')
    // Out of the layout flow: it must not push the transcript up.
    const float = chip().parentElement as HTMLElement
    expect(float.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['absolute', 'bottom-full', 'pointer-events-none'])
    )
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('steps the dot pattern', () => {
    render(<ComposerSandboxChip sandboxStatus={status({})} />)
    expect(litCells()).toBe('000101101')
    act(() => {
      vi.advanceTimersByTime(175)
    })
    expect(litCells()).toBe('100100011')
    act(() => {
      vi.advanceTimersByTime(175 * 7)
    })
    expect(litCells()).toBe('000101101')
  })

  it('opens a full-width list with the backend, compute, and uptime', () => {
    vi.setSystemTime(new Date('2026-11-15T17:10:00Z'))
    const onRefresh = vi.fn()
    render(
      <ComposerSandboxChip
        sandboxStatus={status({ startedAt: '2026-11-15T17:00:00Z' })}
        onRefreshSandbox={onRefresh}
      />
    )
    fireEvent.click(chip())
    const panel = screen.getByRole('dialog', { name: 'Sandboxes' })
    expect(panel.className.split(/\s+/)).toContain('w-full')
    expect(panel.textContent).toContain('1 Sandbox')
    expect(panel.textContent).toContain('Modal')
    expect(panel.textContent).toContain('T4 GPU · 4 CPU · 16 GB RAM')
    expect(panel.textContent).toContain('10m 0s')
    expect(onRefresh).toHaveBeenCalledTimes(1)
    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(panel.textContent).toContain('10m 5s')
  })

  it('keeps the uptime when the chat is left and reopened', () => {
    vi.setSystemTime(new Date('2026-11-15T17:10:00Z'))
    const running = status({ startedAt: '2026-11-15T17:00:00Z' })
    const first = render(<ComposerSandboxChip sandboxStatus={running} />)
    first.unmount()
    vi.setSystemTime(new Date('2026-11-15T17:12:30Z'))
    render(<ComposerSandboxChip sandboxStatus={running} />)
    fireEvent.click(chip())
    expect(screen.getByRole('dialog').textContent).toContain('12m 30s')
  })

  it('closes on Minimize, Escape, and an outside click', () => {
    render(<ComposerSandboxChip sandboxStatus={status({})} />)
    fireEvent.click(chip())
    fireEvent.click(screen.getByRole('button', { name: 'Minimize' }))
    expect(screen.queryByRole('dialog')).toBeNull()

    fireEvent.click(chip())
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()

    fireEvent.click(chip())
    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('dialog')).toBeNull()

    fireEvent.click(chip())
    fireEvent.mouseDown(screen.getByRole('dialog'))
    expect(screen.getByRole('dialog')).toBeTruthy()
  })

  it('stops the sandbox from the row', () => {
    const onStop = vi.fn()
    render(
      <ComposerSandboxChip sandboxStatus={status({})} onSandboxStop={onStop} />
    )
    fireEvent.click(chip())
    fireEvent.click(screen.getByRole('button', { name: 'Stop sandbox' }))
    expect(onStop).toHaveBeenCalledTimes(1)
  })

  it('shows the transition and hides Stop while the sandbox is stopping', () => {
    render(
      <ComposerSandboxChip
        sandboxStatus={status({})}
        sandboxPhase="stopping"
        onSandboxStop={() => undefined}
      />
    )
    fireEvent.click(chip())
    expect(screen.getByRole('dialog').textContent).toContain('Stopping…')
    expect(screen.queryByRole('button', { name: 'Stop sandbox' })).toBeNull()
  })

  it('shows when the sandbox will stop', () => {
    vi.setSystemTime(new Date('2026-11-15T17:10:00Z'))
    render(
      <ComposerSandboxChip
        sandboxStatus={status({
          startedAt: '2026-11-15T17:00:00Z',
          idleTimeoutSeconds: 600,
          maxLifetimeSeconds: 1800,
          lastActiveAt: '2026-11-15T17:07:00Z',
          expiresAt: '2026-11-15T17:30:00Z'
        })}
      />
    )
    fireEvent.click(chip())
    const line = () => screen.getByTestId('sandbox-lifecycle')
    expect(line().textContent).toBe('Stops in 7 min if idle')
    // Both rules, in full, are one hover away.
    expect(line().getAttribute('title')).toBe(
      'Stops after 10 min idle (about 7m 0s left) · 30 min limit (20m 0s left)'
    )
    act(() => {
      vi.advanceTimersByTime(60_000)
    })
    expect(line().textContent).toBe('Stops in 6 min if idle')
  })

  it('keeps a sandbox Modal stopped on screen, with when, why, and Start', () => {
    vi.setSystemTime(new Date('2026-11-15T17:10:00Z'))
    const onStart = vi.fn()
    render(
      <ComposerSandboxChip
        sandboxStatus={status({
          status: 'stopped',
          stoppedAt: '2026-11-15T17:05:50Z',
          stopReason: 'idle',
          idleTimeoutSeconds: 600
        })}
        onSandboxStart={onStart}
        onSandboxStop={() => undefined}
      />
    )
    expect(chip().textContent).toBe('Sandbox stopped')
    fireEvent.click(chip())
    const panel = screen.getByRole('dialog')
    expect(panel.textContent).toContain('Sandbox stopped')
    expect(screen.getByTestId('sandbox-lifecycle').textContent).toBe(
      'Stopped 4 min ago · idle timeout'
    )
    expect(screen.getByTestId('sandbox-lifecycle').getAttribute('title')).toBe(
      'Stopped 4m 10s ago after 10 min idle'
    )
    expect(screen.queryByRole('button', { name: 'Stop sandbox' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Start' }))
    expect(onStart).toHaveBeenCalledTimes(1)
  })

  it('does not linger after the user stops the sandbox', () => {
    const { container } = render(
      <ComposerSandboxChip sandboxStatus={status({ status: 'stopped' })} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('opens the sandbox settings from Edit, inside the card', () => {
    render(
      <MemoryRouter>
        <ComposerSandboxChip
          sandboxStatus={status({})}
          onSandboxBackendSelect={() => undefined}
          onSandboxComputeChange={() => undefined}
        />
      </MemoryRouter>
    )
    fireEvent.click(chip())
    const panel = screen.getByRole('dialog')
    expect(screen.queryByRole('button', { name: 'Confirm' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(panel.contains(screen.getByRole('button', { name: 'Confirm' }))).toBe(
      true
    )
    expect(panel.contains(screen.getByLabelText('Time limit'))).toBe(true)
    // The card is already about a Modal sandbox: no Local/Modal choice here,
    // and no second Stop next to the one on the row.
    expect(screen.queryByRole('switch')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Local' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Stop' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Restart sandbox' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    expect(screen.queryByRole('button', { name: 'Confirm' })).toBeNull()
  })

  it('keeps an edit in progress when the status is re-fetched', () => {
    const props = {
      onSandboxBackendSelect: () => undefined,
      onSandboxComputeChange: () => undefined
    }
    // The T4 preset: the form starts clean, with nothing to confirm.
    const t4 = { cpuCores: 8, ramGb: 32 }
    const view = render(
      <MemoryRouter>
        <ComposerSandboxChip sandboxStatus={status(t4)} {...props} />
      </MemoryRouter>
    )
    fireEvent.click(chip())
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    const confirm = () =>
      screen.getByRole('button', { name: 'Confirm' }) as HTMLButtonElement
    expect(confirm().disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Time limit'), {
      target: { value: String(2 * 3600) }
    })
    expect(confirm().disabled).toBe(false)
    // Same settings, new uptime and idle numbers: the 30 s poll.
    view.rerender(
      <MemoryRouter>
        <ComposerSandboxChip
          sandboxStatus={status({
            ...t4,
            lastActiveAt: '2026-11-15T17:09:30Z'
          })}
          {...props}
        />
      </MemoryRouter>
    )
    expect(confirm().disabled).toBe(false)
  })

  it('saves a longer time limit from the card', async () => {
    const onCompute = vi.fn()
    render(
      <MemoryRouter>
        <ComposerSandboxChip
          sandboxStatus={status({
            cpuCores: 8,
            ramGb: 32,
            idleTimeoutSeconds: 600,
            maxLifetimeSeconds: 1800,
            configuredIdleTimeoutSeconds: 600,
            configuredMaxLifetimeSeconds: 1800
          })}
          onSandboxBackendSelect={() => undefined}
          onSandboxComputeChange={onCompute}
        />
      </MemoryRouter>
    )
    fireEvent.click(chip())
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    const limit = screen.getByLabelText('Time limit') as HTMLSelectElement
    expect(limit.value).toBe('1800')
    expect(screen.getByRole('dialog').textContent).toContain(
      'Modal allows up to 24 h per sandbox.'
    )
    fireEvent.change(limit, { target: { value: String(4 * 3600) } })
    // Modal cannot change a sandbox that is already running.
    expect(screen.getByRole('dialog').textContent).toContain(
      'The running sandbox keeps its current limits. Restart it to use these.'
    )
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    })
    expect(onCompute).toHaveBeenCalledTimes(1)
    expect(onCompute.mock.calls[0][0]).toMatchObject({
      idleTtlSeconds: 600,
      maxLifetimeSeconds: 4 * 3600,
      computeType: 'gpu',
      gpuClass: 'T4'
    })
  })

  it('raises the time limit with the idle timeout', () => {
    render(
      <MemoryRouter>
        <ComposerSandboxChip
          sandboxStatus={status({ cpuCores: 8, ramGb: 32 })}
          onSandboxBackendSelect={() => undefined}
          onSandboxComputeChange={() => undefined}
        />
      </MemoryRouter>
    )
    fireEvent.click(chip())
    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    fireEvent.change(screen.getByLabelText('Stop when idle for'), {
      target: { value: String(2 * 3600) }
    })
    expect(
      (screen.getByLabelText('Time limit') as HTMLSelectElement).value
    ).toBe(String(4 * 3600))
  })
})

describe('sandbox chooser in the + menu', () => {
  afterEach(() => {
    cleanup()
  })

  const t4 = { cpuCores: 8, ramGb: 32 }

  it('is one Modal switch, with no Local tab', () => {
    render(
      <MemoryRouter>
        <ComposerSandboxPicker
          embedded
          sandboxStatus={status(t4)}
          onSandboxBackendSelect={() => undefined}
        />
      </MemoryRouter>
    )
    const toggle = screen.getByRole('switch', { name: 'Use Modal sandbox' })
    expect(toggle.getAttribute('aria-checked')).toBe('true')
    expect(screen.queryByRole('button', { name: 'Local' })).toBeNull()
    expect(screen.getByLabelText('Time limit')).toBeTruthy()
  })

  it('switching Modal off moves the chat back to local', async () => {
    const onBackend = vi.fn()
    render(
      <MemoryRouter>
        <ComposerSandboxPicker
          embedded
          sandboxStatus={status(t4)}
          onSandboxBackendSelect={onBackend}
          onSandboxComputeChange={() => undefined}
        />
      </MemoryRouter>
    )
    fireEvent.click(screen.getByRole('switch', { name: 'Use Modal sandbox' }))
    expect(
      screen
        .getByRole('switch', { name: 'Use Modal sandbox' })
        .getAttribute('aria-checked')
    ).toBe('false')
    // Off means this computer: nothing about Modal left to configure.
    expect(screen.queryByLabelText('Time limit')).toBeNull()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    })
    expect(onBackend).toHaveBeenCalledWith('builtin')
  })

  it('switching Modal on from a local chat saves compute and selects Modal', async () => {
    const onBackend = vi.fn()
    const onCompute = vi.fn()
    render(
      <MemoryRouter>
        <ComposerSandboxPicker
          embedded
          sandboxStatus={status({
            ...t4,
            backend: 'builtin',
            sessionBackend: null,
            status: 'ready'
          })}
          onSandboxBackendSelect={onBackend}
          onSandboxComputeChange={onCompute}
        />
      </MemoryRouter>
    )
    const toggle = screen.getByRole('switch', { name: 'Use Modal sandbox' })
    expect(toggle.getAttribute('aria-checked')).toBe('false')
    fireEvent.click(toggle)
    expect(screen.getByLabelText('Time limit')).toBeTruthy()
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
    })
    expect(onCompute).toHaveBeenCalledTimes(1)
    expect(onBackend).toHaveBeenCalledWith('modal')
  })

  it('cannot be switched on before Modal is set up', () => {
    render(
      <MemoryRouter>
        <ComposerSandboxPicker
          embedded
          sandboxStatus={status({
            backend: 'builtin',
            status: 'ready',
            modalConfigured: false
          })}
          onSandboxBackendSelect={() => undefined}
        />
      </MemoryRouter>
    )
    const toggle = screen.getByRole('switch', {
      name: 'Use Modal sandbox'
    }) as HTMLButtonElement
    expect(toggle.disabled).toBe(true)
    expect(screen.getByRole('link', { name: 'Set up' })).toBeTruthy()
  })
})
