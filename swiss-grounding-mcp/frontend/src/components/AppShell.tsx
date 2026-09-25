import type { ReactNode } from "react";
import type { Page } from "../navigation/usePage";
import { HomeIcon, WorkflowIcon } from "../workflow/icons";

export function AppShell({ page, onNavigate, children }: {
  page: Page;
  onNavigate: (page: Page) => void;
  children: ReactNode;
}) {
  return <div className={page === "workflow" ? "workflow-shell" : "home-shell"}>
    <nav className="app-nav" aria-label="Primary navigation">
      <strong>Swiss Grounding</strong>
      <div>
        <button type="button" aria-current={page === "home" ? "page" : undefined} onClick={() => onNavigate("home")}>
          <HomeIcon className="nav-icon" /><span>Home</span>
        </button>
        <button type="button" aria-current={page === "workflow" ? "page" : undefined} onClick={() => onNavigate("workflow")}>
          <WorkflowIcon className="nav-icon" /><span>Workflow</span>
        </button>
      </div>
    </nav>
    <main className="app-content">{children}</main>
  </div>;
}
