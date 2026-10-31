import { describe, expect, it } from "vitest";
import { draftData, fieldData } from "./draft";

const square: GeoJSON.Polygon = {
  type: "Polygon",
  coordinates: [[[7, 51], [7.01, 51], [7.01, 51.01], [7, 51.01], [7, 51]]],
};

describe("draft helpers", () => {
  it("is empty without geometry", () => {
    expect(fieldData(null).features).toHaveLength(0);
    expect(draftData([]).features).toHaveLength(0);
  });

  it("wraps a saved polygon as one feature", () => {
    expect(fieldData(square).features).toHaveLength(1);
  });

  it("shows one point per click and an open line for two points", () => {
    const data = draftData([[7, 51], [7.01, 51]]);
    expect(data.features).toHaveLength(3);
    const line = data.features[2].geometry as GeoJSON.LineString;
    expect(line.coordinates).toHaveLength(2);
  });

  it("closes the preview line with three points", () => {
    const data = draftData([[7, 51], [7.01, 51], [7.01, 51.01]]);
    const line = data.features[3].geometry as GeoJSON.LineString;
    expect(line.coordinates).toHaveLength(4);
    expect(line.coordinates[3]).toEqual([7, 51]);
  });
});
