import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MlMap, StyleSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

interface Props {
  basemap: string;
  geometry: GeoJSON.Polygon | null;
  onPoint: (lon: number, lat: number) => void;
  onPolygon: (geometry: GeoJSON.Polygon) => void;
}

const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

export default function Map({ basemap, geometry, onPoint, onPolygon }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const [drawing, setDrawing] = useState(false);
  const points = useRef<[number, number][]>([]);
  const geometryRef = useRef<GeoJSON.Polygon | null>(geometry);
  geometryRef.current = geometry;

  useEffect(() => {
    if (!container.current || map.current) return;
    const style: StyleSpecification =
      basemap === "osm"
        ? {
            version: 8 as const,
            sources: {
              osm: {
                type: "raster" as const,
                tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
                tileSize: 256,
                attribution: "© OpenStreetMap-Mitwirkende",
              },
            },
            layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
          }
        : {
            version: 8,
            sources: {},
            layers: [
              { id: "bg", type: "background", paint: { "background-color": "#141a17" } },
            ],
          };

    const instance = new maplibregl.Map({
      container: container.current,
      style,
      center: [10.0, 51.2],
      zoom: 5.4,
    });
    instance.addControl(new maplibregl.NavigationControl(), "top-left");
    instance.on("load", () => {
      instance.addSource("field", {
        type: "geojson",
        data: geometryRef.current
          ? { type: "Feature", properties: {}, geometry: geometryRef.current }
          : EMPTY,
      });
      instance.addLayer({ id: "field-fill", type: "fill", source: "field",
        paint: { "fill-color": "#7fd48b", "fill-opacity": 0.18 } });
      instance.addLayer({ id: "field-line", type: "line", source: "field",
        paint: { "line-color": "#7fd48b", "line-width": 2 } });
      instance.addSource("draft", { type: "geojson", data: EMPTY });
      instance.addLayer({ id: "draft-line", type: "line", source: "draft",
        paint: { "line-color": "#f0b45a", "line-width": 2 } });
    });
    map.current = instance;
    return () => { instance.remove(); map.current = null; };
  }, [basemap]);

  useEffect(() => {
    const instance = map.current;
    if (!instance || !instance.getSource("field")) return;
    (instance.getSource("field") as maplibregl.GeoJSONSource).setData(
      geometry ? { type: "Feature", properties: {}, geometry } : EMPTY
    );
  }, [geometry]);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const handler = (event: maplibregl.MapMouseEvent) => {
      const [lon, lat] = [event.lngLat.lng, event.lngLat.lat];
      if (!drawing) { onPoint(lon, lat); return; }
      points.current.push([lon, lat]);
      const ring = points.current;
      const draft = {
        type: "Feature" as const,
        properties: {},
        geometry: ring.length > 1
          ? { type: "LineString" as const, coordinates: ring }
          : { type: "Point" as const, coordinates: ring[0] },
      };
      (instance.getSource("draft") as maplibregl.GeoJSONSource).setData(draft as never);
      if (ring.length >= 3) {
        const closed = [...ring, ring[0]];
        onPolygon({ type: "Polygon", coordinates: [closed] });
      }
    };
    instance.on("click", handler);
    return () => { instance.off("click", handler); };
  }, [drawing, onPoint, onPolygon]);

  return (
    <div className="map">
      <div ref={container} style={{ position: "absolute", inset: 0 }} />
      <button
        className="ghost"
        style={{ position: "absolute", top: 12, right: 12, zIndex: 2 }}
        onClick={() => { points.current = []; setDrawing((d) => !d); }}
      >
        {drawing ? "Zeichnen beenden" : "Feld zeichnen"}
      </button>
      {basemap !== "osm" && (
        <div
          className="muted"
          style={{ position: "absolute", left: 12, bottom: 12, zIndex: 2, maxWidth: 320 }}
        >
          Leere Basiskarte: Feld direkt auf die Flaeche zeichnen oder die App mit
          {" "}<code>--basemap osm</code> neu installieren.
        </div>
      )}
    </div>
  );
}
