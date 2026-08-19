import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { getHealth, listProductions, PRODUCTION_ID } from "../lib/api";

const STORAGE_KEY = "cc_selected_production";
const ProductionContext = createContext(null);

export const ProductionProvider = ({ children }) => {
  const [productions, setProductions] = useState([]);
  const [selectedId, setSelectedId] = useState(
    () => localStorage.getItem(STORAGE_KEY) || PRODUCTION_ID
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const health = await getHealth();
      if (!health?.clickhouse?.connected) {
        setProductions([]);
        setError(null);
        return [];
      }
      const data = await listProductions();
      const list = data?.productions || [];
      setProductions(list);
      setError(null);
      // Keep selection valid: fall back to demo, then first available.
      setSelectedId((cur) => {
        if (list.some((p) => p.production_id === cur)) return cur;
        const fallback =
          (list.find((p) => p.production_id === PRODUCTION_ID) || list[0])?.production_id || cur;
        return fallback;
      });
      return list;
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Failed to load productions");
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (selectedId) localStorage.setItem(STORAGE_KEY, selectedId);
  }, [selectedId]);

  const select = useCallback((id) => {
    if (!id) return;
    // Switching production invalidates the active case pointer.
    localStorage.removeItem("cc_active_case");
    setSelectedId(id);
  }, []);

  const selected = useMemo(
    () => productions.find((p) => p.production_id === selectedId) || null,
    [productions, selectedId]
  );

  const value = useMemo(
    () => ({ productions, selectedId, selected, loading, error, refresh, select }),
    [productions, selectedId, selected, loading, error, refresh, select]
  );

  return <ProductionContext.Provider value={value}>{children}</ProductionContext.Provider>;
};

export const useProduction = () => {
  const ctx = useContext(ProductionContext);
  if (!ctx) throw new Error("useProduction must be used within a ProductionProvider");
  return ctx;
};
