import React, { useEffect, useRef, useState, useCallback } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useTheme } from "../context/ThemeContext";
import { MapPin, Globe, Layers, AlertCircle, Search, Compass, Check } from "lucide-react";

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

    marker.on("dragend", (e) => {
      const pos = e.target.getLatLng();
      const nextCoords = { lat: Number(pos.lat.toFixed(6)), lng: Number(pos.lng.toFixed(6)) };
      setCurrentCoords(nextCoords);
      if (onChange) onChange(nextCoords);
    });

    markerRef.current = marker;

    if (interactive) {
      map.on("click", (e) => {
        const { lat, lng } = e.latlng;
        const nextCoords = { lat: Number(lat.toFixed(6)), lng: Number(lng.toFixed(6)) };
        marker.setLatLng([nextCoords.lat, nextCoords.lng]);
        setCurrentCoords(nextCoords);
        if (onChange) onChange(nextCoords);
      });
    }

    mapInstanceRef.current = map;

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
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
          searchQuery
        )}&limit=1`,
        { headers: { "User-Agent": "ContinuityCouncil/1.0" } }
      );
      const data = await res.json();
      if (data && data.length > 0) {
        const nextLat = parseFloat(data[0].lat);
        const nextLng = parseFloat(data[0].lon);
        const nextCoords = { lat: Number(nextLat.toFixed(6)), lng: Number(nextLng.toFixed(6)) };

        setCurrentCoords(nextCoords);
        if (markerRef.current) markerRef.current.setLatLng([nextLat, nextLng]);
        mapInstanceRef.current.setView([nextLat, nextLng], 14, { animate: true });
        if (onChange) onChange(nextCoords);
      }
    } catch (err) {
      console.warn("Geocoding failed:", err);
    } finally {
      setIsSearching(false);
    }
  };

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
              placeholder={locationName ? `Search '${locationName}'...` : "Search city, studio, address..."}
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

      {/* Fallback Warning Notice */}
      {isFallback && (
        <div className="absolute bottom-2 left-2.5 z-[1000] flex items-center gap-1.5 rounded-[7px] border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-600 dark:text-amber-400 backdrop-blur-sm shadow-sm">
          <AlertCircle className="h-3 w-3" />
          <span>Active Basemap: OpenStreetMap Standard (Tile Fallback)</span>
        </div>
      )}
    </div>
  );
};
