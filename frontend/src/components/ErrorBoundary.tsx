import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  failed: boolean;
}

/** Last line of defence: a render crash shows a recover card, never a blank screen. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Echo UI error:", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="crash" role="alert">
        <div className="crash-card">
          <h1>Something went wrong on this page</h1>
          <p>Your conversations on the server are safe. Reload to start a new chat.</p>
          <button onClick={() => window.location.reload()}>Start new chat</button>
        </div>
      </div>
    );
  }
}
