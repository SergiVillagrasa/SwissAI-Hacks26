import { describe, expect, it } from "vitest";
import { DISPLAYABLE_STATUSES, WIDGET_COMPONENTS } from "./widgetRegistry";

describe("widgetRegistry", () => {
  it("has a component and a displayable-status list for every widget type", () => {
    const expectedTypes = [
      "train_connections", "station_board", "fares", "disruptions",
      "flight", "flight_search", "airport_guidance", "flight_to_train",
    ];
    for (const type of expectedTypes) {
      expect(WIDGET_COMPONENTS[type]).toBeDefined();
      expect(DISPLAYABLE_STATUSES[type]).toBeDefined();
    }
  });

  it("only treats success/fallback_link as displayable for fares", () => {
    expect(DISPLAYABLE_STATUSES.fares).toEqual(["success", "fallback_link"]);
  });

  it("only treats ok as displayable for train connections", () => {
    expect(DISPLAYABLE_STATUSES.train_connections).toEqual(["ok"]);
  });
});
