import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AirportGuidanceCard } from "./AirportGuidanceCard";

describe("AirportGuidanceCard", () => {
  it("renders the guidance text and its citation link", () => {
    render(
      <AirportGuidanceCard
        data={{
          topic: "transfers",
          guidance: "Check the departure time and gate on the flight information screens.",
          source: "Flughafen Zürich AG",
          source_url: "https://www.flughafen-zuerich.ch/en/passengers/fly/all-about-the-flight/transfer",
        }}
      />
    );

    expect(screen.getByText(/departure time and gate/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /flughafen zürich ag/i })).toHaveAttribute(
      "href",
      "https://www.flughafen-zuerich.ch/en/passengers/fly/all-about-the-flight/transfer"
    );
  });
});
