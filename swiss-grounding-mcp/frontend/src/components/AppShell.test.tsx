import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppShell } from "./AppShell";


describe("AppShell", () => {
  it("shows exactly Home and Workflow and navigates between them", () => {
    render(<AppShell page="home" onNavigate={() => {}}><div>content</div></AppShell>);
    expect(screen.getAllByRole("button")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Home" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Workflow" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Workflow" }));
  });
});
