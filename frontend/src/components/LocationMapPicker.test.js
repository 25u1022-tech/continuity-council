import React from "react";
import { BASEMAP_URLS, ATTRIBUTIONS, TIER_OPTIONS, CURRENCY_SYMBOLS } from "./LocationMapPicker";

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

  test("defines correct OSM city tier multipliers", () => {
    const tier1 = TIER_OPTIONS.find((t) => t.value === "tier_1");
    const tier2 = TIER_OPTIONS.find((t) => t.value === "tier_2");
    const tier3 = TIER_OPTIONS.find((t) => t.value === "tier_3");

    expect(tier1.mult).toBe(1.0);
    expect(tier2.mult).toBe(0.5);
    expect(tier3.mult).toBe(0.35);
  });

  test("contains currency symbols for major filming jurisdictions", () => {
    expect(CURRENCY_SYMBOLS.USD).toBe("$");
    expect(CURRENCY_SYMBOLS.EUR).toBe("€");
    expect(CURRENCY_SYMBOLS.GBP).toBe("£");
    expect(CURRENCY_SYMBOLS.INR).toBe("₹");
    expect(CURRENCY_SYMBOLS.BRL).toBe("R$");
    expect(CURRENCY_SYMBOLS.NGN).toBe("₦");
  });

  test("computes compound geo multiplier accurately", () => {
    // Dharwad: India (0.29) x Tier 2 (0.5) = 0.145 -> ~0.15
    const computeGeoMult = (countryMult, tierMult) =>
      Math.round((countryMult * tierMult + Number.EPSILON) * 100) / 100;
    expect(computeGeoMult(0.29, 0.5)).toBe(0.15);

    // London: UK (0.83) x Tier 1 (1.0) = 0.83
    expect(computeGeoMult(0.83, 1.0)).toBe(0.83);

    // Sao Paulo: Brazil (0.44) x Tier 1 (1.0) = 0.44
    expect(computeGeoMult(0.44, 1.0)).toBe(0.44);

    // Small town in Nigeria: Nigeria (0.25) x Tier 3 (0.35) = 0.0875 -> 0.09
    expect(computeGeoMult(0.25, 0.35)).toBe(0.09);
  });


});
