import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { StatusBanner } from "./StatusBanner";

describe("StatusBanner", () => {
  it("renders the honest message for an out_of_scope status", () => {
    render(<StatusBanner status="out_of_scope" message="Taxes are not covered by this assistant." candidates={[]} onClarify={() => {}} />);

    expect(screen.getByText(/not covered/i)).toBeInTheDocument();
  });

  it("renders clickable candidate chips for needs_clarification and resends the choice", () => {
    const onClarify = vi.fn();
    render(
      <StatusBanner
        status="needs_clarification"
        message="Which Fribourg did you mean?"
        candidates={[{ name: "Fribourg/Freiburg", stop_ref: "8504100", probability: null }]}
        onClarify={onClarify}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Fribourg/Freiburg" }));

    expect(onClarify).toHaveBeenCalledWith("Fribourg/Freiburg");
  });
});
