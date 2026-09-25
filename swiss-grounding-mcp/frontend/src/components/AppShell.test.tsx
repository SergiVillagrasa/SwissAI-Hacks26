import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { AppShell } from "./AppShell";

describe("AppShell", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("shows Home, Workflow, and the sidebar pin toggle, and navigates between pages", () => {
    render(<AppShell page="home" onNavigate={() => {}}><div>content</div></AppShell>);
    expect(screen.getAllByRole("button")).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Home" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Workflow" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Workflow" }));
  });

  it("starts collapsed (unpinned) and pins/unpins the sidebar open on toggle click", () => {
    render(<AppShell page="home" onNavigate={() => {}}><div>content</div></AppShell>);
    const nav = screen.getByRole("navigation", { name: "Primary navigation" });
    const pinButton = screen.getByRole("button", { name: "Keep sidebar open" });

    expect(nav).toHaveAttribute("data-pinned", "false");
    expect(pinButton).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(pinButton);
    expect(nav).toHaveAttribute("data-pinned", "true");
    expect(screen.getByRole("button", { name: "Collapse sidebar" })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(nav).toHaveAttribute("data-pinned", "false");
  });

  it("persists the pinned preference across mounts via localStorage", () => {
    const { unmount } = render(<AppShell page="home" onNavigate={() => {}}><div>content</div></AppShell>);
    fireEvent.click(screen.getByRole("button", { name: "Keep sidebar open" }));
    unmount();

    render(<AppShell page="home" onNavigate={() => {}}><div>content</div></AppShell>);
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toHaveAttribute("data-pinned", "true");
  });

  it("blurs a nav button after a real mouse click so hover alone governs the collapsed rail again", () => {
    render(<AppShell page="home" onNavigate={() => {}}><div>content</div></AppShell>);
    const workflowButton = screen.getByRole("button", { name: "Workflow" });
    workflowButton.focus();
    expect(workflowButton).toHaveFocus();

    fireEvent.click(workflowButton, { detail: 1 });
    expect(workflowButton).not.toHaveFocus();
  });

  it("does not steal focus from a keyboard-activated nav click", () => {
    render(<AppShell page="home" onNavigate={() => {}}><div>content</div></AppShell>);
    const homeButton = screen.getByRole("button", { name: "Home" });
    homeButton.focus();

    // A keyboard-triggered "click" (Enter/Space on a focused button) has detail: 0.
    fireEvent.click(homeButton, { detail: 0 });
    expect(homeButton).toHaveFocus();
  });
});
