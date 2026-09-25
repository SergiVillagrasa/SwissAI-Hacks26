import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FaresCard } from "./FaresCard";

const fares = [
  { product: "Supersaver ticket", price_chf: 22.6, class_of_travel: "2", discount: null },
  { product: "Single ticket", price_chf: 31, class_of_travel: "2", discount: null },
];

const bookingUrl = "https://sbb.ch/en?von=Bern&nach=Z%C3%BCrich%20HB&date=2026-10-15";

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

  it("shows a Book on SBB button next to live fares that opens the official site in a new tab", () => {
    render(<FaresCard data={{ fares, booking_url: bookingUrl }} />);

    const link = screen.getByRole("link", { name: /book on sbb/i });
    expect(link).toHaveAttribute("href", bookingUrl);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
  });

  it("shows the applied ordering badge when fares were sorted by price", () => {
    render(<FaresCard data={{ fares, booking_url: bookingUrl, sorted_by: "price" }} />);

    expect(screen.getByTestId("sort-badge")).toHaveTextContent("Sorted by: Cheapest");
  });

  it("renders no ordering badge when no sorting was applied", () => {
    render(<FaresCard data={{ fares, booking_url: bookingUrl }} />);

    expect(screen.queryByTestId("sort-badge")).not.toBeInTheDocument();
  });
});
