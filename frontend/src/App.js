import React, { useLayoutEffect, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { Shell } from "./components/layout/Shell";
import { ProductionProvider } from "./context/ProductionContext";
import { ThemeProvider, useTheme } from "./context/ThemeContext";
import DashboardPage from "./pages/DashboardPage";
import ReportDisruptionPage from "./pages/ReportDisruptionPage";
import InvestigationPage from "./pages/InvestigationPage";
import DecisionLedgerPage from "./pages/DecisionLedgerPage";
import DataMethodologyPage from "./pages/DataMethodologyPage";
import SettingsPage from "./pages/SettingsPage";
import "./App.css";
import { hasColdStart, onColdStart } from "./lib/api";

function AppContent() {
  const { theme } = useTheme();
  const [activeCaseId, setActiveCaseIdState] = useState(
    () => localStorage.getItem("cc_active_case") || ""
  );
  const [activeCase, setActiveCase] = useState(null);
  const [coldStart, setColdStart] = useState(() => hasColdStart());

  const setActiveCaseId = (id) => {
    setActiveCaseIdState(id);
    if (id) localStorage.setItem("cc_active_case", id);
    else localStorage.removeItem("cc_active_case");
  };

  useLayoutEffect(() => onColdStart(() => setColdStart(true)), []);

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
        </Shell>
      </ProductionProvider>

      <Toaster position="bottom-right" theme={theme === "light" ? "light" : "dark"} richColors />
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AppContent />
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
