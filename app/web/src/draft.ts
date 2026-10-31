export const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

export function fieldData(geometry: GeoJSON.Polygon | null): GeoJSON.FeatureCollection {
  return geometry
    ? {
        type: "FeatureCollection",
        features: [{ type: "Feature", properties: {}, geometry }],
      }
    : EMPTY;
}

export function draftData(points: [number, number][]): GeoJSON.FeatureCollection {
  if (points.length === 0) return EMPTY;
  const features: GeoJSON.Feature[] = points.map((point) => ({
    type: "Feature",
    properties: {},
    geometry: { type: "Point", coordinates: point },
  }));
  if (points.length > 1) {
    features.push({
      type: "Feature",
      properties: {},
      geometry: {
        type: "LineString",
        coordinates: points.length >= 3 ? [...points, points[0]] : points,
      },
    });
  }
  return { type: "FeatureCollection", features };
}
