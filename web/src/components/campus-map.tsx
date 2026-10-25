"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import { Map as MapLibreMap, Marker, setWorkerUrl } from "maplibre-gl";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import type { Area, Place } from "@/lib/types";

// Copied into /public by scripts/copy-map-worker.mjs on install.
setWorkerUrl("/maplibre-gl-worker.mjs");

/** OpenStreetMap vector tiles (OpenFreeMap), restyled below in Haggle's palette. */
const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";
const CAMPUS: [[number, number], [number, number]] = [
  [-111.9425, 33.4092],
  [-111.9232, 33.4268],
];

// Quiet greys from the site palette; pine marks zones, ink marks meeting spots.
const COLORS = {
  paper: "#f5f5f1",
  lawn: "#e4ebdd",
  water: "#dde6e6",
  residential: "#f0f0ea",
  block: "#e8e8e3",
  blockEdge: "#dcdcd5",
  road: "#ffffff",
  roadEdge: "#e2e2dc",
  ink: "#161716",
  muted: "#8a8c85",
  pine: "#2e5b4f",
};

const HIDE = /boundary|shield|airport|label_(country|state|city|town|village)|aeroway|railway/;

function paint(map: MapLibreMap, id: string, prop: string, value: unknown) {
  // Layer property names vary by layer type; the style is ours to restyle.
  map.setPaintProperty(id, prop as never, value as never);
}

/** Recolour the base map so it reads as campus paper, not a navigation app. */
function restyle(map: MapLibreMap) {
  for (const layer of map.getStyle().layers ?? []) {
    const { id, type } = layer;
    if (HIDE.test(id)) {
      map.setLayoutProperty(id, "visibility", "none");
      continue;
    }
    if (type === "background") paint(map, id, "background-color", COLORS.paper);
    else if (id === "park" || id === "landcover_wood") paint(map, id, "fill-color", COLORS.lawn);
    else if (id === "water") paint(map, id, "fill-color", COLORS.water);
    else if (id === "landuse_residential") paint(map, id, "fill-color", COLORS.residential);
    else if (id === "building") {
      paint(map, id, "fill-color", COLORS.block);
      paint(map, id, "fill-outline-color", COLORS.blockEdge);
    } else if (type === "line" && id.includes("casing")) paint(map, id, "line-color", COLORS.roadEdge);
    else if (type === "line" && id.startsWith("highway")) paint(map, id, "line-color", COLORS.road);
    else if (type === "symbol") {
      paint(map, id, "text-color", COLORS.muted);
      paint(map, id, "text-halo-color", COLORS.paper);
    }
  }
}

function zonesGeoJSON(areas: Record<string, Area>) {
  return {
    type: "FeatureCollection" as const,
    features: Object.entries(areas).map(([key, a]) => {
      const [[w, s], [e, n]] = a.bounds;
      return {
        type: "Feature" as const,
        properties: { area: key },
        geometry: { type: "Polygon" as const, coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] },
      };
    }),
  };
}

function zoneLabel(area: Area, active: boolean): HTMLElement {
  const el = document.createElement("div");
  el.style.cssText = `font-family: var(--font-sans); font-weight: 600; font-size: 12px; pointer-events: none;
    color: ${active ? COLORS.pine : COLORS.ink}; text-shadow: 0 0 3px #fff, 0 0 3px #fff;`;
  el.textContent = area.label.replace(" campus", "");
  return el;
}

function spotMarker(place: Place, highlight: boolean): HTMLElement {
  const el = document.createElement("div");
  const size = highlight ? 12 : 8;
  el.title = place.name + (place.curbside ? " (curbside)" : "");
  el.setAttribute("aria-label", el.title);
  el.style.cssText = `width:${size}px;height:${size}px;background:${COLORS.ink};transform:rotate(45deg);
    outline:2px solid #fff;cursor:default;`;
  return el;
}

/**
 * The real ASU Tempe map.
 *  - browse: all zones; click one to filter listings (other filters in `query` are kept).
 *  - focus:  one zone (a listing's area) and its meeting spots, fixed view.
 *  - pickup: a single meeting spot.
 */
export function CampusMap({
  areas,
  places,
  activeArea,
  mode = "browse",
  spotId,
  query = "",
  className = "",
}: {
  areas: Record<string, Area>;
  places: Place[];
  activeArea?: string;
  mode?: "browse" | "focus" | "pickup";
  spotId?: string;
  query?: string;
  className?: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    if (!container.current) return;
    const interactive = mode === "browse";
    const spot = places.find((p) => p.place_id === spotId);
    const focus = activeArea && areas[activeArea];

    const map = new MapLibreMap({
      container: container.current,
      style: STYLE_URL,
      bounds: focus && mode === "focus" ? focus.bounds : CAMPUS,
      fitBoundsOptions: { padding: 10 },
      interactive,
      // A small map in a scrolling page shouldn't capture the scroll wheel.
      scrollZoom: false,
      dragRotate: false,
      pitchWithRotate: false,
      attributionControl: { compact: true },
    });
    if (spot && mode === "pickup") map.jumpTo({ center: [spot.lng, spot.lat], zoom: 16.4 });

    const markers: Marker[] = [];
    map.on("load", () => {
      restyle(map);
      const visibleAreas =
        mode === "browse" ? areas : activeArea && areas[activeArea] ? { [activeArea]: areas[activeArea] } : {};

      map.addSource("zones", { type: "geojson", data: zonesGeoJSON(visibleAreas) });
      map.addLayer({
        id: "zone-fill",
        type: "fill",
        source: "zones",
        paint: {
          "fill-color": COLORS.pine,
          "fill-opacity": ["case", ["==", ["get", "area"], activeArea ?? ""], 0.1, 0],
        },
      });
      map.addLayer({
        id: "zone-line",
        type: "line",
        source: "zones",
        paint: {
          "line-color": COLORS.pine,
          "line-width": 1,
          "line-opacity": ["case", ["==", ["get", "area"], activeArea ?? ""], 1, 0.45],
        },
      });

      if (mode !== "pickup") {
        for (const [key, a] of Object.entries(visibleAreas)) {
          markers.push(
            new Marker({ element: zoneLabel(a, key === activeArea), anchor: "top-left" })
              .setLngLat([a.bounds[0][0] + 0.0004, a.bounds[1][1] - 0.0002])
              .addTo(map),
          );
        }
      }
      const shown =
        mode === "pickup" ? places.filter((p) => p.place_id === spotId)
        : mode === "focus" ? places.filter((p) => p.area === activeArea)
        : places;
      for (const p of shown) {
        markers.push(
          new Marker({ element: spotMarker(p, mode !== "browse") }).setLngLat([p.lng, p.lat]).addTo(map),
        );
      }

      if (interactive) {
        map.on("click", "zone-fill", (e) => {
          const area = e.features?.[0]?.properties?.area as string | undefined;
          if (!area) return;
          const params = new URLSearchParams(query);
          if (area === activeArea) params.delete("area");
          else params.set("area", area);
          router.push(params.size ? `/?${params}` : "/", { scroll: false });
        });
        map.on("mouseenter", "zone-fill", () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "zone-fill", () => (map.getCanvas().style.cursor = ""));
      }
    });

    return () => {
      markers.forEach((m) => m.remove());
      map.remove();
    };
    // The map is rebuilt only when what it shows changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, spotId, activeArea, query]);

  return <div ref={container} className={`h-full min-h-[320px] w-full ${className}`} role="region" aria-label="Map of ASU Tempe campus" />;
}
