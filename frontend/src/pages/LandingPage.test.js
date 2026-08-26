import React, { act } from "react";
import { createRoot } from "react-dom/client";
import LandingPage from "./LandingPage";
import { ThemeProvider } from "../context/ThemeContext";

global.IS_REACT_ACT_ENVIRONMENT = true;

const mockNavigate = jest.fn();

jest.mock(
  "react-router-dom",
  () => ({
    useNavigate: () => mockNavigate,
    Link: ({ to, children, ...props }) => (
      <a href={to} {...props}>
        {children}
      </a>
    ),
  }),
  { virtual: true }
);

describe("LandingPage Component", () => {
  let container = null;
  let root = null;

  beforeEach(() => {
    mockNavigate.mockClear();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(async () => {
    await act(async () => {
      root.unmount();
    });
    container.remove();
    container = null;
  });

  test("renders hero title, tagline, description, and highlight cards", async () => {
    await act(async () => {
      root.render(
        <ThemeProvider>
          <LandingPage />
        </ThemeProvider>
      );
    });

    const page = container.querySelector('[data-testid="landing-page"]');
    expect(page).not.toBeNull();

    // Check title & tagline
    expect(container.textContent).toContain("Continuity Council");
    expect(container.textContent).toContain(
      "Real-time shoot recovery powered by Google ADK, ClickHouse intelligence, and Gemini."
    );

    // Check CTA button
    const ctaBtn = container.querySelector('[data-testid="landing-cta-button"]');
    expect(ctaBtn).not.toBeNull();
    expect(ctaBtn.textContent).toContain("Launch Production Council");

    // Check core highlights
    expect(container.textContent).toContain("Multi-Agent Council (Google ADK)");
    expect(container.textContent).toContain("Empirical Historical Grounding (ClickHouse)");
    expect(container.textContent).toContain("Live External Signals");
    expect(container.textContent).toContain("Interactive Production Chatbot & Voice");
    expect(container.textContent).toContain("Audited Decision Ledger");
    expect(container.textContent).toContain("AI Production Intake");
  });

  test("clicking CTA button triggers navigation to /dashboard", async () => {
    await act(async () => {
      root.render(
        <ThemeProvider>
          <LandingPage />
        </ThemeProvider>
      );
    });

    const ctaBtn = container.querySelector('[data-testid="landing-cta-button"]');
    expect(ctaBtn).not.toBeNull();

    await act(async () => {
      ctaBtn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(mockNavigate).toHaveBeenCalledWith("/dashboard");
  });
});
