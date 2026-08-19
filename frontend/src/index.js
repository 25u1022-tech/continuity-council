import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";

// Suppress the benign React 18 dev-mode "ResizeObserver loop" warning so it
// never triggers the error overlay during demos. Other errors are unaffected.
const resizeObserverErr = window.Error; window.addEventListener('error', (e) => { if (e.message.includes('ResizeObserver loop')) { e.stopImmediatePropagation(); } });
// Belt-and-braces: if the dev-server overlay was already registered before this
// listener, hide its iframe for this specific benign warning only.
window.addEventListener("error", (e) => {
  if (e.message && e.message.includes("ResizeObserver loop")) {
    const overlay = document.getElementById("webpack-dev-server-client-overlay");
    const overlayDiv = document.getElementById("webpack-dev-server-client-overlay-div");
    if (overlay) overlay.style.display = "none";
    if (overlayDiv) overlayDiv.style.display = "none";
  }
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
    },
  },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
