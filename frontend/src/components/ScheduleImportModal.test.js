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

  test("shows replacement warning in separate dialog on confirm and handles cancel & confirmation", async () => {
    jest.useFakeTimers();
    api.uploadSchedulePDF.mockResolvedValueOnce({ job_id: "job_test_warning" });
    api.getScheduleImportJob.mockResolvedValueOnce({
      job_id: "job_test_warning",
      status: "ready",
      preview: {
        days_count: 5,
        scenes_count: 8,
        cast_count: 4,
        locations_count: 4,
        sample_scenes: [
          { scene_number: "SC-001", scene_title: "Opening Sequence", location_name: "Grand Ballroom", shoot_day: 1, int_ext: "INT" },
        ],
        sample_cast: ["Mara Voss", "Dev Okafor"],
        sample_locations: ["Grand Ballroom"],
      },
    });
    api.confirmScheduleImport.mockResolvedValueOnce({ success: true, production_id: "prod_001", scenes_count: 8 });

    const mockImportComplete = jest.fn();

    await act(async () => {
      root.render(
        <ScheduleImportModal
          open={true}
          onOpenChange={() => {}}
          productionId="prod_001"
          currentSceneCount={3}
          onImportComplete={mockImportComplete}
        />
      );
    });

    // 1. Initially on idle - separate confirmation dialog must NOT be open
    expect(document.querySelector('[data-testid="schedule-import-confirm-dialog"]')).toBeNull();

    // 2. Select file to transition to preview
    const fileInput = document.querySelector('[data-testid="schedule-pdf-input"]');
    const fakeFile = new File(["%PDF-1.4 test"], "schedule.pdf", { type: "application/pdf" });

    await act(async () => {
      const event = new Event("change", { bubbles: true });
      Object.defineProperty(fileInput, "files", { value: [fakeFile], writable: true });
      fileInput.dispatchEvent(event);
    });

    // Fast-forward polling interval
    await act(async () => {
      jest.advanceTimersByTime(1600);
    });

    // 3. In preview stage, separate confirmation dialog is not yet open
    expect(document.querySelector('[data-testid="schedule-preview-container"]')).not.toBeNull();
    expect(document.querySelector('[data-testid="schedule-import-confirm-dialog"]')).toBeNull();

    // 4. Click initial "Confirm import" button
    const confirmBtn = document.querySelector('[data-testid="confirm-schedule-import-btn"]');
    expect(confirmBtn).not.toBeNull();

    await act(async () => {
      confirmBtn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    // 5. Separate confirmation dialog must now open with exact dynamic counts and warning
    const confirmDialog = document.querySelector('[data-testid="schedule-import-confirm-dialog"]');
    expect(confirmDialog).not.toBeNull();
    expect(confirmDialog.textContent).toContain("Replace current production schedule?");
    expect(confirmDialog.textContent).toContain("This will replace the current 3 scenes with 8 new scenes. This action cannot be undone.");

    // 6. Test Cancel action closes the separate confirmation dialog
    const cancelBtn = document.querySelector('[data-testid="cancel-replace-schedule-btn"]');
    expect(cancelBtn).not.toBeNull();

    await act(async () => {
      cancelBtn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });
    expect(document.querySelector('[data-testid="schedule-import-confirm-dialog"]')).toBeNull();

    // 7. Click confirm import again to re-open confirmation dialog and proceed
    const reConfirmBtn = document.querySelector('[data-testid="confirm-schedule-import-btn"]');
    await act(async () => {
      reConfirmBtn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const finalConfirmBtn = document.querySelector('[data-testid="confirm-replace-schedule-btn"]');
    expect(finalConfirmBtn).not.toBeNull();

    await act(async () => {
      finalConfirmBtn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    expect(api.confirmScheduleImport).toHaveBeenCalledWith("job_test_warning");
    expect(mockImportComplete).toHaveBeenCalledWith({ success: true, production_id: "prod_001", scenes_count: 8 });

    jest.useRealTimers();
  });
});
