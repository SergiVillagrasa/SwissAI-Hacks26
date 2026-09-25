import { Component, type ReactNode } from "react";

export class WorkflowBoundary extends Component<{
  children: ReactNode;
  onGoHome: () => void;
}, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return <section className="workflow-page workflow-empty">
        <h1>The workflow view could not be displayed</h1>
        <p>Your request may still be running. Return Home to continue using the assistant.</p>
        <button type="button" onClick={this.props.onGoHome}>Go to Home</button>
      </section>;
    }
    return this.props.children;
  }
}
