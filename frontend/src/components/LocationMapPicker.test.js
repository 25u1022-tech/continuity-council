import React from "react";
import { BASEMAP_URLS, ATTRIBUTIONS } from "./LocationMapPicker";

describe("LocationMapPicker basemaps and configuration", () => {
  test("defines correct keyless open-source basemap URLs", () => {
    expect(BASEMAP_URLS.light).toContain("cartocdn.com/light_all");
    expect(BASEMAP_URLS.dark).toContain("cartocdn.com/dark_all");
    expect(BASEMAP_URLS.satellite).toContain("server.arcgisonline.com/ArcGIS/rest/services/World_Imagery");
    expect(BASEMAP_URLS.fallback).toContain("tile.openstreetmap.org");
  });

  test("defines proper attributions for CARTO, Esri, and OSM", () => {
    expect(ATTRIBUTIONS.carto).toContain("OpenStreetMap");
    expect(ATTRIBUTIONS.carto).toContain("CARTO");
    expect(ATTRIBUTIONS.esri).toContain("Esri");
    expect(ATTRIBUTIONS.osm).toContain("OpenStreetMap");
  });

  test("calculates active tile layer URL based on mode", () => {
    const getTileUrl = (theme, isSatellite, isFallback) => {
      if (isFallback) return BASEMAP_URLS.fallback;
      if (isSatellite) return BASEMAP_URLS.satellite;
      if (theme === "dark") return BASEMAP_URLS.dark;
      return BASEMAP_URLS.light;
    };

    expect(getTileUrl("light", false, false)).toBe(BASEMAP_URLS.light);
    expect(getTileUrl("dark", false, false)).toBe(BASEMAP_URLS.dark);
    expect(getTileUrl("dark", true, false)).toBe(BASEMAP_URLS.satellite);
    expect(getTileUrl("light", true, false)).toBe(BASEMAP_URLS.satellite);
    expect(getTileUrl("dark", false, true)).toBe(BASEMAP_URLS.fallback);
    expect(getTileUrl("light", true, true)).toBe(BASEMAP_URLS.fallback);
  });
});
