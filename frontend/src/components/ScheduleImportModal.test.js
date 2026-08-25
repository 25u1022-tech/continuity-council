import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { ScheduleImportModal } from "./ScheduleImportModal";
import * as api from "../lib/api";

global.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("../lib/api", () => ({
  uploadSchedulePDF: jest.fn(),
  getScheduleImportJob: jest.fn(),
  confirmScheduleImport: jest.fn(),
}));

describe("ScheduleImportModal", () => {
  let container = null;
  let root = null;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    jest.clearAllMocks();
  });

  afterEach(async () => {
    await act(async () => {
      if (root) root.unmount();
    });
    if (container) container.remove();
    container = null;
  });

  test("renders dropzone in idle stage", async () => {
    await act(async () => {
      root.render(
        <ScheduleImportModal
          open={true}
          onOpenChange={() => {}}
          productionId="prod_001"
          onImportComplete={() => {}}
        />
      );
    });

    const dropzone = document.querySelector('[data-testid="pdf-dropzone"]');
    expect(dropzone).not.toBeNull();
    expect(document.body.textContent).toContain("Drop your shooting schedule or call sheet PDF here");
  });

  test("handles file upload and transitions to preview on ready", async () => {
    api.uploadSchedulePDF.mockResolvedValueOnce({ job_id: "job_test_123" });
    api.getScheduleImportJob.mockResolvedValueOnce({
      job_id: "job_test_123",
      status: "ready",
      preview: {
        days_count: 3,
        scenes_count: 12,
        cast_count: 4,
        locations_count: 2,
        sample_scenes: [
          {
            scene_number: "1",
            scene_title: "Harbor Arrival",
            location_name: "Harbor Pier 7",
            shoot_day: 1,
            int_ext: "EXT",
          },
        ],
        sample_cast: ["Mara Voss", "Dev Okafor"],
        sample_locations: ["Harbor Pier 7", "Stage A"],
      },
    });

    await act(async () => {
      root.render(
        <ScheduleImportModal
          open={true}
          onOpenChange={() => {}}
          productionId="prod_001"
          onImportComplete={() => {}}
        />
      );
    });

    const fileInput = document.querySelector('[data-testid="schedule-pdf-input"]');
    expect(fileInput).not.toBeNull();

    const fakeFile = new File(["%PDF-1.4 test"], "callsheet.pdf", {
      type: "application/pdf",
    });

    await act(async () => {
      const event = new Event("change", { bubbles: true });
      Object.defineProperty(fileInput, "files", {
        value: [fakeFile],
        writable: true,
      });
      fileInput.dispatchEvent(event);
    });

    expect(api.uploadSchedulePDF).toHaveBeenCalledWith("prod_001", fakeFile);
  });
});
