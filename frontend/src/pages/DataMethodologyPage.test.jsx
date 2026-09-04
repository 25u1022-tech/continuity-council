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
    expect(provenanceCard.textContent).toContain("The 200,000-row historical corpus is synthetic, grounded in real public archives.");
    expect(provenanceCard.textContent).toContain("Open-Meteo Historical Weather 2019–2024");
    expect(provenanceCard.textContent).toContain("OSM Filming Hubs (60 Verified Locations)");
    expect(provenanceCard.textContent).toContain("SAG-AFTRA / IATSE Published Rate Cards");
    expect(provenanceCard.textContent).toContain("IMDb / TheNumbers Budget Percentiles");
    expect(provenanceCard.textContent).toContain("Mumbai Monsoon");
    expect(provenanceCard.textContent).toContain("8.17x monsoon surge, Jun-Sep");
    expect(provenanceCard.textContent).toContain("Jul peak 234");
  });
});
