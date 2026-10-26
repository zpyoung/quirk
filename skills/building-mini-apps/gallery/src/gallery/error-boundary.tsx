import { Component, type ErrorInfo, type ReactNode } from "react"

import { ErrorState } from "@/components/mini/states"

interface Props {
  children: ReactNode
  /** Changing this value clears a caught error, e.g. when the route changes. */
  resetKey: string
}

/** Keeps one pattern's runtime failure from blanking the whole gallery. */
export class ErrorBoundary extends Component<Props, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidUpdate(prev: Props) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null })
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (error) {
      return <ErrorState error={error} onRetry={() => this.setState({ error: null })} />
    }
    return this.props.children
  }
}
