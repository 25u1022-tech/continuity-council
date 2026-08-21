import React, { useLayoutEffect, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { Shell } from "./components/layout/Shell";
import { ProductionProvider } from "./context/ProductionContext";
import { ThemeProvider, useTheme } from "./context/ThemeContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import DashboardPage from "./pages/DashboardPage";
import ReportDisruptionPage from "./pages/ReportDisruptionPage";
import InvestigationPage from "./pages/InvestigationPage";
import RecoveryOptionsPage from "./pages/RecoveryOptionsPage";
import DecisionLedgerPage from "./pages/DecisionLedgerPage";
import DataMethodologyPage from "./pages/DataMethodologyPage";
import SettingsPage from "./pages/SettingsPage";
import "./App.css";
import { hasColdStart, onColdStart } from "./lib/api";
import { safeStorage } from "./lib/storage";

function AppContent() {
  const { theme } = useTheme();
  const [activeCaseId, setActiveCaseIdState] = useState(
    () => safeStorage.getItem("cc_active_case", "")
  );
  const [activeCase, setActiveCase] = useState(null);
  const [coldStart, setColdStart] = useState(() => {
    try {
      return Boolean(hasColdStart());
    } catch {
      return false;
    }
  });

  const setActiveCaseId = (id) => {
    setActiveCaseIdState(id || "");
    if (id) safeStorage.setItem("cc_active_case", id);
    else safeStorage.removeItem("cc_active_case");
  };

  useLayoutEffect(() => {
    try {
      return onColdStart(() => setColdStart(true));
    } catch {
      return undefined;
    }
  }, []);

  return (
    <>
      <ProductionProvider>
        {coldStart && (
          <div
            role="status"
            className="border-b border-[var(--cc-border)] bg-[var(--cc-surface-hover)] px-6 py-2.5 text-center text-[13px] text-[var(--cc-text-primary)]"
          >
            Starting production services — the first visit can take a few seconds.
          </div>
        )}
        <Shell activeCase={activeCase}>
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<DashboardPage activeCaseId={activeCaseId} />} />
              <Route
                path="/report"
                element={<ReportDisruptionPage setActiveCaseId={setActiveCaseId} />}
              />
              <Route
                path="/investigation"
                element={
                  <InvestigationPage caseId={activeCaseId} onCaseUpdate={setActiveCase} />
                }
              />
              <Route
                path="/options"
                element={
                  <RecoveryOptionsPage caseId={activeCaseId} onCaseUpdate={setActiveCase} />
                }
              />
              <Route path="/ledger" element={<DecisionLedgerPage />} />
              <Route path="/methodology" element={<DataMethodologyPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </ErrorBoundary>
        </Shell>
      </ProductionProvider>

      <Toaster position="bottom-right" theme={theme === "light" ? "light" : "dark"} richColors />
    </>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ThemeProvider>
          <AppContent />
        </ThemeProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
