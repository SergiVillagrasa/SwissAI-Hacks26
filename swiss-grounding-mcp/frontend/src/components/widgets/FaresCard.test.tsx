import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FaresCard } from "./FaresCard";

describe("FaresCard", () => {
  it("renders fare products when available", () => {
    render(
      <FaresCard
        data={{ fares: [{ product: "Saver Day Pass", price_chf: 39, class_of_travel: "2", discount: null }], booking_url: null }}
      />
    );

    expect(screen.getByText("Saver Day Pass")).toBeInTheDocument();
    expect(screen.getByText(/CHF 39/)).toBeInTheDocument();
  });

  it("renders the SBB booking deep link when no live fare was available", () => {
    render(<FaresCard data={{ fares: [], booking_url: "https://www.sbb.ch/en/timetable.html?x" }} />);

    expect(screen.getByRole("link", { name: /book on sbb/i })).toHaveAttribute(
      "href",
      "https://www.sbb.ch/en/timetable.html?x"
    );
  });
});
