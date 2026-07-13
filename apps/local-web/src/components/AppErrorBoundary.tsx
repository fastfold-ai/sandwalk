import { Component, type ErrorInfo, type ReactNode } from 'react'

import { ErrorPage } from '@/components/ErrorPage'

type Props = {
  children: ReactNode
  /** Optional compact panel instead of full-page layout. */
  variant?: 'page' | 'panel'
  onReset?: () => void
  resetKeys?: unknown[]
}

type State = {
  error: Error | null
}

/**
 * Catches render/lifecycle crashes anywhere under it and shows ErrorPage
 * with message + stack. Use around the app shell and around dashboard panes.
 */
export class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('[AppErrorBoundary]', error, info.componentStack)
  }

  componentDidUpdate(prevProps: Props): void {
    if (!this.state.error || !this.props.resetKeys) return
    const prev = prevProps.resetKeys || []
    const next = this.props.resetKeys
    if (
      prev.length !== next.length ||
      prev.some((value, index) => value !== next[index])
    ) {
      this.setState({ error: null })
    }
  }

  private reset = () => {
    this.setState({ error: null })
    this.props.onReset?.()
  }

  render() {
    if (this.state.error) {
      return (
        <ErrorPage
          error={this.state.error}
          variant={this.props.variant ?? 'page'}
          onRetry={this.reset}
          retryLabel="Reload view"
          className={this.props.variant === 'panel' ? 'm-6' : undefined}
        />
      )
    }
    return this.props.children
  }
}
