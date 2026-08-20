import React, { useEffect, useRef, useState, useCallback } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useTheme } from "../context/ThemeContext";
import { resolveGeoEconomics } from "../lib/api";
import {
  MapPin, Globe, Layers, AlertCircle, Search, Compass, Check,
  ChevronDown, DollarSign, Sparkles, Building, Info,
} from "lucide-react";

// Basemap Tile Providers (Keyless, Open-Source)
export const BASEMAP_URLS = {
  light: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  dark: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  satellite: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  fallback: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
};

export const ATTRIBUTIONS = {
  carto: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors &copy; <a href=\"https://carto.com/attributions\">CARTO</a>",
  esri: "&copy; <a href=\"https://www.esri.com/\">Esri</a>",
  osm: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors",
};

export const CURRENCY_SYMBOLS = {
  USD: "$",
  EUR: "€",
  GBP: "£",
  INR: "₹",
  BRL: "R$",
  NGN: "₦",
  CAD: "C$",
  AUD: "A$",
  JPY: "¥",
  AED: "د.إ",
  JOD: "JD",
  CHF: "CHF",
  CNY: "¥",
  KRW: "₩",
  MXN: "Mex$",
  ZAR: "R",
  SGD: "S$",
  NZD: "NZ$",
  SEK: "kr",
  NOK: "kr",
  DKK: "kr",
  PLN: "zł",
  THB: "฿",
  IDR: "Rp",
  MYR: "RM",
  PHP: "₱",
  TRY: "₺",
  SAR: "﷼",
  ARS: "$",
  COP: "$",
};

export const TIER_OPTIONS = [
  { value: "tier_1", label: "Tier 1 (Metro)", mult: 1.0, desc: "Population ≥5M or Capital / Megacity" },
  { value: "tier_2", label: "Tier 2 (Regional)", mult: 0.5, desc: "Population 200k–1M or Secondary City" },
  { value: "tier_3", label: "Tier 3 (Small)", mult: 0.35, desc: "Population <200k Town / Rural" },
];

// Custom Minimalist SVG Pin Icon (Apple aesthetic)
const createPinIcon = (isDark = false) => {
  const pinBg = isDark ? "#F5F5F7" : "#1C1C1E";
  const pinDot = isDark ? "#0B0B0E" : "#FFFFFF";
  return L.divIcon({
    className: "cc-custom-map-pin",
    html: `
      <div style="
        position: relative;
        width: 28px;
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        filter: drop-shadow(0 4px 6px rgba(0,0,0,0.3));
        cursor: grab;
      ">
        <svg viewBox="0 0 24 32" width="28" height="36" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M12 0C5.372 0 0 5.373 0 12c0 9 12 20 12 20s12-11 12-20c0-6.627-5.372-12-12-12z" fill="${pinBg}"/>
          <circle cx="12" cy="12" r="4.5" fill="${pinDot}"/>
        </svg>
      </div>
    `,
    iconSize: [28, 36],
    iconAnchor: [14, 34],
    popupAnchor: [0, -32],
  });
};

export const LocationMapPicker = ({
  latitude = 34.0522,
  longitude = -118.2437,
  onChange,
  locationName = "",
  cityTier = "tier_1",
  countryCode = "US",
  currency = "USD",
  geoMult = 1.0,
  height = "280px",
  interactive = true,
  className = "",
}) => {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const tileLayerRef = useRef(null);
  const markerRef = useRef(null);
  const tileErrorCountRef = useRef(0);

  const { theme } = useTheme();
  const [isSatellite, setIsSatellite] = useState(false);
  const [isFallback, setIsFallback] = useState(false);
  const [currentCoords, setCurrentCoords] = useState({
    lat: Number(latitude) || 34.0522,
    lng: Number(longitude) || -118.2437,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  // Geo-Aware Economics State
  const [geoState, setGeoState] = useState({
    country_code: countryCode || "US",
    country_name: "United States",
    city_name: locationName || "Los Angeles",
    city_tier: cityTier || "tier_1",
    tier_mult: cityTier === "tier_1" ? 1.0 : cityTier === "tier_2" ? 0.5 : 0.35,
    country_mult: 1.0,
    geo_mult: geoMult || 1.0,
    currency_code: currency || "USD",
    population: null,
    is_capital: false,
    source_note: "World Bank open data (CC-BY 4.0) + OSM Nominatim",
    warning: "",
  });

  const [tierOverrideOpen, setTierOverrideOpen] = useState(false);

  // Determine active tile URL and attribution
  const getActiveTileConfig = useCallback(
    (currentTheme, satelliteMode, fallbackMode) => {
      if (fallbackMode) {
        return {
          url: BASEMAP_URLS.fallback,
          attribution: ATTRIBUTIONS.osm,
          maxZoom: 19,
          subdomains: ["a", "b", "c"],
        };
      }
      if (satelliteMode) {
        return {
          url: BASEMAP_URLS.satellite,
          attribution: ATTRIBUTIONS.esri,
          maxZoom: 18,
          subdomains: [],
        };
      }
      if (currentTheme === "dark") {
        return {
          url: BASEMAP_URLS.dark,
          attribution: ATTRIBUTIONS.carto,
          maxZoom: 20,
          subdomains: "abcd",
        };
      }
      return {
        url: BASEMAP_URLS.light,
        attribution: ATTRIBUTIONS.carto,
        maxZoom: 20,
        subdomains: "abcd",
      };
    },
    []
  );

  // Helper to resolve geo economics for a query / coordinates
  const resolveGeo = useCallback(
    async (query, lat, lng, userTierOverride = null) => {
      try {
        const data = await resolveGeoEconomics(query, lat, lng);
        if (data) {
          const effectiveTier = userTierOverride || data.city_tier || "tier_1";
          const effectiveTierMult =
            effectiveTier === "tier_1" ? 1.0 : effectiveTier === "tier_2" ? 0.5 : 0.35;
          const countryMult = Number(data.country_mult) || 1.0;
          const calculatedGeoMult =
            Math.round((countryMult * effectiveTierMult + Number.EPSILON) * 100) / 100;

          const updated = {


            ...data,
            city_tier: effectiveTier,
            tier_mult: effectiveTierMult,
            country_mult: countryMult,
            geo_mult: calculatedGeoMult,
          };
          setGeoState(updated);

          if (onChange) {
            onChange({
              lat: Number(lat.toFixed(6)),
              lng: Number(lng.toFixed(6)),
              latitude: Number(lat.toFixed(6)),
              longitude: Number(lng.toFixed(6)),
              country_code: updated.country_code,
              country_name: updated.country_name,
              city_tier: updated.city_tier,
              currency_code: updated.currency_code,
              country_mult: updated.country_mult,
              geo_mult: updated.geo_mult,
            });
          }
          return updated;
        }
      } catch (err) {
        console.warn("Geo economics resolution error:", err);
      }
      return null;
    },
    [onChange]
  );

  // Initialize map once on mount
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    const initialLat = Number(latitude) || 34.0522;
    const initialLng = Number(longitude) || -118.2437;
    const initialZoom = initialLat !== 0 || initialLng !== 0 ? 12 : 3;

    const map = L.map(mapContainerRef.current, {
      center: [initialLat, initialLng],
      zoom: initialZoom,
      zoomControl: false,
      attributionControl: true,
    });

    L.control.zoom({ position: "bottomright" }).addTo(map);

    const config = getActiveTileConfig(theme, isSatellite, isFallback);
    const tileLayer = L.tileLayer(config.url, {
      attribution: config.attribution,
      maxZoom: config.maxZoom,
      subdomains: config.subdomains,
    }).addTo(map);

    tileLayer.on("tileerror", () => {
      tileErrorCountRef.current += 1;
      if (tileErrorCountRef.current >= 3 && !isFallback) {
        setIsFallback(true);
      }
    });

    tileLayerRef.current = tileLayer;

    // Place Initial Marker
    const icon = createPinIcon(theme === "dark");
    const marker = L.marker([initialLat, initialLng], {
      icon,
      draggable: interactive,
    }).addTo(map);

    marker.on("dragend", async (e) => {
      const pos = e.target.getLatLng();
      const nextCoords = { lat: Number(pos.lat.toFixed(6)), lng: Number(pos.lng.toFixed(6)) };
      setCurrentCoords(nextCoords);
      await resolveGeo(locationName || `${nextCoords.lat},${nextCoords.lng}`, nextCoords.lat, nextCoords.lng);
    });

    markerRef.current = marker;

    if (interactive) {
      map.on("click", async (e) => {
        const { lat, lng } = e.latlng;
        const nextCoords = { lat: Number(lat.toFixed(6)), lng: Number(lng.toFixed(6)) };
        marker.setLatLng([nextCoords.lat, nextCoords.lng]);
        setCurrentCoords(nextCoords);
        await resolveGeo(locationName || `${nextCoords.lat},${nextCoords.lng}`, nextCoords.lat, nextCoords.lng);
      });
    }

    mapInstanceRef.current = map;

    // Initial resolution
    if (locationName) {
      resolveGeo(locationName, initialLat, initialLng);
    }

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Seamless Tile Layer Swap on Theme/Satellite change (WITHOUT REMOUNTING)
  useEffect(() => {
    if (!tileLayerRef.current || !mapInstanceRef.current) return;

    const config = getActiveTileConfig(theme, isSatellite, isFallback);
    tileLayerRef.current.setUrl(config.url);
    if (mapInstanceRef.current.attributionControl) {
      mapInstanceRef.current.attributionControl.setPrefix(false);
    }

    // Update marker pin style
    if (markerRef.current) {
      markerRef.current.setIcon(createPinIcon(theme === "dark"));
    }
  }, [theme, isSatellite, isFallback, getActiveTileConfig]);

  // Sync external coordinates changes
  useEffect(() => {
    const lat = Number(latitude);
    const lng = Number(longitude);
    if (!isNaN(lat) && !isNaN(lng) && mapInstanceRef.current && markerRef.current) {
      if (Math.abs(currentCoords.lat - lat) > 0.0001 || Math.abs(currentCoords.lng - lng) > 0.0001) {
        markerRef.current.setLatLng([lat, lng]);
        mapInstanceRef.current.setView([lat, lng], mapInstanceRef.current.getZoom());
        setCurrentCoords({ lat, lng });
      }
    }
  }, [latitude, longitude]); // eslint-disable-line react-hooks/exhaustive-deps

  // Live Geocoding Search via OpenStreetMap Nominatim
  const handleSearch = async (e) => {
    e?.preventDefault();
    if (!searchQuery.trim() || !mapInstanceRef.current) return;

    setIsSearching(true);
    try {
      const geo = await resolveGeo(searchQuery.trim(), currentCoords.lat, currentCoords.lng);
      if (geo && geo.latitude && geo.longitude) {
        const nextLat = Number(geo.latitude.toFixed(6));
        const nextLng = Number(geo.longitude.toFixed(6));
        const nextCoords = { lat: nextLat, lng: nextLng };

        setCurrentCoords(nextCoords);
        if (markerRef.current) markerRef.current.setLatLng([nextLat, nextLng]);
        mapInstanceRef.current.setView([nextLat, nextLng], 13, { animate: true });
      }
    } catch (err) {
      console.warn("Geocoding search failed:", err);
    } finally {
      setIsSearching(false);
    }
  };

  // User Tier Override handler
  const handleTierOverride = (newTier) => {
    const tierMult = newTier === "tier_1" ? 1.0 : newTier === "tier_2" ? 0.5 : 0.35;
    const countryMult = Number(geoState.country_mult) || 1.0;
    const newGeoMult = Math.round((countryMult * tierMult + Number.EPSILON) * 100) / 100;

    const updated = {

      ...geoState,
      city_tier: newTier,
      tier_mult: tierMult,
      geo_mult: newGeoMult,
    };
    setGeoState(updated);
    setTierOverrideOpen(false);


    if (onChange) {
      onChange({
        lat: currentCoords.lat,
        lng: currentCoords.lng,
        latitude: currentCoords.lat,
        longitude: currentCoords.lng,
        country_code: updated.country_code,
        country_name: updated.country_name,
        city_tier: updated.city_tier,
        currency_code: updated.currency_code,
        country_mult: updated.country_mult,
        geo_mult: updated.geo_mult,
      });
    }
  };

  const currSymbol = CURRENCY_SYMBOLS[geoState.currency_code] || geoState.currency_code;
  const tierDisplay = geoState.city_tier ? geoState.city_tier.replace("_", "-") : "tier-1";

  return (
    <div
      className={`relative overflow-hidden rounded-[12px] border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)] ${className}`}
      data-testid="location-map-picker"
    >
      {/* Map Surface */}
      <div
        ref={mapContainerRef}
        style={{ height, width: "100%" }}
        className="z-0"
      />

      {/* Floating Header Control Bar */}
      <div className="absolute top-2.5 left-2.5 right-2.5 z-[1000] flex items-center justify-between gap-2 pointer-events-none">
        {/* Search Bar */}
        {interactive && (
          <form
            onSubmit={handleSearch}
            className="pointer-events-auto flex items-center gap-1.5 rounded-[9px] border border-[var(--cc-border)] bg-[var(--cc-surface)]/95 backdrop-blur-md px-2.5 py-1.5 shadow-sm cc-transition hover:border-[var(--cc-border-strong)]"
          >
            <Search className="h-3.5 w-3.5 text-[var(--cc-text-tertiary)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={locationName ? `Search '${locationName}'...` : "Search city, country (e.g. Dharwad)..."}
              className="w-44 bg-transparent text-[12px] text-[var(--cc-text-primary)] placeholder:text-[var(--cc-text-quaternary)] focus:outline-none"
            />
            {isSearching && (
              <span className="text-[11px] text-[var(--cc-text-tertiary)] animate-pulse">...</span>
            )}
          </form>
        )}

        {/* Action Toggles */}
        <div className="pointer-events-auto flex items-center gap-1.5">
          {/* Satellite Layer Toggle */}
          <button
            type="button"
            onClick={() => setIsSatellite((prev) => !prev)}
            data-testid="satellite-toggle-btn"
            className={`flex items-center gap-1 rounded-[9px] border px-2.5 py-1.5 text-[12px] font-medium shadow-sm cc-transition backdrop-blur-md ${
              isSatellite
                ? "border-[var(--cc-text-primary)] bg-[var(--cc-text-primary)] text-[var(--cc-canvas)]"
                : "border-[var(--cc-border)] bg-[var(--cc-surface)]/95 text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)]"
            }`}
            title="Toggle Satellite Imagery (Esri)"
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Satellite</span>
          </button>

          {/* Coordinates Badge */}
          <div className="hidden sm:flex items-center gap-1 rounded-[9px] border border-[var(--cc-border)] bg-[var(--cc-surface)]/95 backdrop-blur-md px-2.5 py-1.5 text-[11px] font-mono text-[var(--cc-text-secondary)] shadow-sm">
            <Compass className="h-3 w-3 text-[var(--cc-text-tertiary)]" />
            <span>
              {currentCoords.lat.toFixed(4)}, {currentCoords.lng.toFixed(4)}
            </span>
          </div>
        </div>
      </div>

      {/* Floating Bottom Geo-Aware Costing Chip & Override Bar */}
      <div className="absolute bottom-2.5 left-2.5 right-2.5 z-[1000] flex flex-wrap items-center justify-between gap-2 pointer-events-none">
        {/* Main Geo Economics Chip */}
        <div
          data-testid="location-geo-chip"
          className="pointer-events-auto flex items-center gap-2 rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface)]/95 backdrop-blur-md px-3 py-1.5 text-[12px] shadow-md font-medium text-[var(--cc-text-primary)]"
        >
          <div className="flex items-center gap-1.5">
            <Globe className="h-3.5 w-3.5 text-[var(--cc-text-secondary)]" />
            <span className="font-semibold text-[var(--cc-text-primary)]">
              {geoState.country_name || geoState.country_code}
            </span>
            <span className="text-[var(--cc-text-tertiary)]">·</span>
            <span className="capitalize text-[var(--cc-text-secondary)]">{tierDisplay}</span>
            <span className="text-[var(--cc-text-tertiary)]">·</span>
            <span className="font-mono font-semibold text-[var(--cc-text-primary)]">
              x{Number(geoState.geo_mult || 1.0).toFixed(2)}
            </span>
          </div>

          <div className="h-3.5 w-[1px] bg-[var(--cc-border)] mx-0.5" />

          {/* Currency Display */}
          <div className="flex items-center gap-1 text-[11px] font-mono text-[var(--cc-text-secondary)]">
            <span className="font-bold text-[var(--cc-text-primary)]">{currSymbol}</span>
            <span>{geoState.currency_code}</span>
          </div>

          {/* Tier Override Dropdown Trigger */}
          <div className="relative">
            <button
              type="button"
              data-testid="tier-override-dropdown-btn"
              onClick={() => setTierOverrideOpen((prev) => !prev)}
              className="flex items-center gap-1 rounded-[6px] border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-2 py-0.5 text-[11px] text-[var(--cc-text-secondary)] hover:text-[var(--cc-text-primary)] hover:border-[var(--cc-border-strong)] cc-transition"
            >
              <span>Override</span>
              <ChevronDown className="h-3 w-3 text-[var(--cc-text-tertiary)]" />
            </button>

            {/* Dropdown Menu */}
            {tierOverrideOpen && (
              <div
                data-testid="tier-override-menu"
                className="absolute bottom-full left-0 mb-1.5 w-52 rounded-[10px] border border-[var(--cc-border)] bg-[var(--cc-surface)] p-1.5 shadow-xl backdrop-blur-md z-[1100]"
              >
                <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--cc-text-tertiary)]">
                  Select City Tier
                </div>
                {TIER_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    data-testid={`tier-option-${opt.value}`}
                    onClick={() => handleTierOverride(opt.value)}
                    className={`flex w-full items-start justify-between gap-2 rounded-[7px] px-2 py-1.5 text-left text-[12px] cc-transition ${
                      geoState.city_tier === opt.value
                        ? "bg-[var(--cc-surface-hover)] font-medium text-[var(--cc-text-primary)]"
                        : "text-[var(--cc-text-secondary)] hover:bg-[var(--cc-surface-hover)] hover:text-[var(--cc-text-primary)]"
                    }`}
                  >
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span>{opt.label}</span>
                        <span className="font-mono text-[11px] opacity-75">({opt.mult}x)</span>
                      </div>
                      <div className="text-[10px] text-[var(--cc-text-tertiary)] leading-tight mt-0.5">
                        {opt.desc}
                      </div>
                    </div>
                    {geoState.city_tier === opt.value && (
                      <Check className="h-3.5 w-3.5 shrink-0 text-[var(--cc-text-primary)] mt-0.5" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Warning badge if fallback */}
        {geoState.warning && (
          <div className="pointer-events-auto flex items-center gap-1.5 rounded-[7px] border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-[11px] text-amber-600 dark:text-amber-400 backdrop-blur-sm shadow-sm">
            <AlertCircle className="h-3 w-3" />
            <span>{geoState.warning}</span>
          </div>
        )}
      </div>

      {/* Fallback Warning Notice */}
      {isFallback && (
        <div className="absolute top-12 left-2.5 z-[1000] flex items-center gap-1.5 rounded-[7px] border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-600 dark:text-amber-400 backdrop-blur-sm shadow-sm">
          <AlertCircle className="h-3 w-3" />
          <span>Active Basemap: OpenStreetMap Standard (Tile Fallback)</span>
        </div>
      )}
    </div>
  );
};
