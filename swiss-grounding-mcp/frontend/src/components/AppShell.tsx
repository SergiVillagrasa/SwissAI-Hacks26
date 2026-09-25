import { useEffect, useState, type MouseEvent, type ReactNode } from "react";
import type { Page } from "../navigation/usePage";
import { HomeIcon, SidebarPinIcon, WorkflowIcon } from "../workflow/icons";

/**
 * A mouse click leaves the button focused, and :focus-within keeps the
 * collapsed rail expanded even after the pointer has moved away — so
 * navigating and then moving the mouse elsewhere would otherwise leave
 * the sidebar stuck open until something else stole focus. Blur it so
 * hover alone governs the expanded state again. MouseEvent.detail is 0
 * for a keyboard-activated click (Enter/Space), so keyboard users keep
 * focus — and the expanded rail — after navigating.
 */
function blurIfMouseClick(event: MouseEvent<HTMLButtonElement>) {
  if (event.detail > 0) event.currentTarget.blur();
}

const PINNED_STORAGE_KEY = "swiss-grounding:sidebar-pinned";

function readPinned(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(PINNED_STORAGE_KEY) === "true";
  } catch (error) {
    console.warn("Unable to read sidebar pinned state from localStorage", error);
    return false;
  }
}

export function AppShell({ page, onNavigate, children }: {
  page: Page;
  onNavigate: (page: Page) => void;
  children: ReactNode;
}) {
  const [pinned, setPinned] = useState<boolean>(readPinned);

  useEffect(() => {
    try {
      window.localStorage.setItem(PINNED_STORAGE_KEY, String(pinned));
    } catch (error) {
      // localStorage unavailable (e.g. private mode) — pinned state just won't persist.
      console.warn("Unable to persist sidebar pinned state to localStorage", error);
    }
  }, [pinned]);

  return <div className={page === "workflow" ? "workflow-shell" : "home-shell"}>
    <nav className="app-nav" aria-label="Primary navigation" data-pinned={pinned}>
      <div className="app-nav__header">
        <span className="nav-icon-slot"><span className="app-nav__mark" aria-hidden>S</span></span>
        <strong className="nav-label">Swiss Grounding</strong>
        <button
          type="button"
          className="app-nav__pin"
          aria-pressed={pinned}
          aria-label={pinned ? "Collapse sidebar" : "Keep sidebar open"}
          title={pinned ? "Collapse sidebar" : "Keep sidebar open"}
          onClick={(event) => {
            setPinned((current) => !current);
            blurIfMouseClick(event);
          }}
        >
          <SidebarPinIcon className="pin-icon" />
        </button>
      </div>
      <div>
        <button
          type="button"
          aria-current={page === "home" ? "page" : undefined}
          onClick={(event) => {
            onNavigate("home");
            blurIfMouseClick(event);
          }}
        >
          <span className="nav-icon-slot"><HomeIcon className="nav-icon" /></span><span className="nav-label">Home</span>
        </button>
        <button
          type="button"
          aria-current={page === "workflow" ? "page" : undefined}
          onClick={(event) => {
            onNavigate("workflow");
            blurIfMouseClick(event);
          }}
        >
          <span className="nav-icon-slot"><WorkflowIcon className="nav-icon" /></span><span className="nav-label">Workflow</span>
        </button>
      </div>
    </nav>
    <main className="app-content">{children}</main>
  </div>;
}
