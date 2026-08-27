import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { LocationMoodboardModal } from "./LocationMoodboardModal";
import * as api from "../lib/api";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("../lib/api", () => ({
  getLocationMoodboard: jest.fn(),
}));

describe("LocationMoodboardModal", () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    jest.clearAllMocks();
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  it("does not render content when closed", async () => {
    await act(async () => {
      root.render(
        <LocationMoodboardModal
          open={false}
          onOpenChange={jest.fn()}
          locationId="loc_002"
        />
      );
    });

    expect(document.querySelector('[data-testid="location-moodboard-modal"]')).toBeNull();
    expect(api.getLocationMoodboard).not.toHaveBeenCalled();
  });

  it("renders image and caption on ready response", async () => {
    api.getLocationMoodboard.mockResolvedValueOnce({
      status: "ready",
      location_id: "loc_002",
      location_name: "Harbor Pier 7 Exterior",
      image_base64: "fakebase64imagebytes==",
      prompt: "Cinematic film still, 35mm motion picture photography...",
      cached: true,
    });

    await act(async () => {
      root.render(
        <LocationMoodboardModal
          open={true}
          onOpenChange={jest.fn()}
          locationId="loc_002"
          locationName="Harbor Pier 7 Exterior"
        />
      );
    });

    // Wait for promise resolution
    await act(async () => {
      await Promise.resolve();
    });

    const modal = document.querySelector('[data-testid="location-moodboard-modal"]');
    expect(modal).not.toBeNull();

    const readyState = document.querySelector('[data-testid="moodboard-ready-state"]');
    expect(readyState).not.toBeNull();

    const img = document.querySelector('[data-testid="moodboard-image"]');
    expect(img).not.toBeNull();
    expect(img.getAttribute("src")).toContain("fakebase64imagebytes==");
    expect(modal.textContent).toContain("Harbor Pier 7 Exterior");
    expect(modal.textContent).toContain("AI-generated preview (Gemini image generation) — Harbor Pier 7 Exterior");
    expect(modal.textContent).toContain("Cached");
  });

  it("renders graceful fallback card on failure or unavailable status", async () => {
    api.getLocationMoodboard.mockResolvedValueOnce({
      status: "unavailable",
      location_id: "loc_002",
      detail: "Imagen 3 generation quota exceeded.",
    });

    await act(async () => {
      root.render(
        <LocationMoodboardModal
          open={true}
          onOpenChange={jest.fn()}
          locationId="loc_002"
          locationName="Downtown Loft"
        />
      );
    });

    await act(async () => {
      await Promise.resolve();
    });

    const unavailableState = document.querySelector('[data-testid="moodboard-unavailable-state"]');
    expect(unavailableState).not.toBeNull();
    expect(unavailableState.textContent).toContain("Visual preview currently unavailable");
    expect(unavailableState.textContent).toContain("select and execute this recovery option");
  });
});
