import React, { act } from "react";
import { createRoot } from "react-dom/client";
import DataMethodologyPage from "./DataMethodologyPage";

global.IS_REACT_ACT_ENVIRONMENT = true;

describe("DataMethodologyPage Component", () => {
  let container = null;
  let root = null;

  beforeEach(() => {
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

  it("renders Historical Corpus Provenance card and Mumbai weather proof chart", async () => {
    await act(async () => {
      root.render(<DataMethodologyPage />);
    });

    const page = container.querySelector('[data-testid="data-methodology-page"]');
    expect(page).not.toBeNull();

    const provenanceCard = container.querySelector('[data-testid="corpus-provenance-card"]');
    expect(provenanceCard).not.toBeNull();
    expect(provenanceCard.textContent).toContain("Historical Corpus Provenance");
    expect(provenanceCard.textContent).toContain("Open-Meteo Weather Archives");
    expect(provenanceCard.textContent).toContain("60 Filming Hubs");
    expect(provenanceCard.textContent).toContain("Union Rate Cards");
    expect(provenanceCard.textContent).toContain("Budget Percentiles");
    expect(provenanceCard.textContent).toContain("Mumbai Monsoon");
    expect(provenanceCard.textContent).toContain("Monsoon Surge");
    expect(provenanceCard.textContent).toContain("Jul");
  });
});
