import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useCasePolling, TERMINAL_STATUSES } from "./useCasePolling";
import * as api from "../lib/api";

global.IS_REACT_ACT_ENVIRONMENT = true;
jest.mock("../lib/api");

describe("useCasePolling hook", () => {
  let container = null;
  let root = null;

  beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
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
    jest.useRealTimers();
  });

  async function renderHookHelper(hookFn) {
    let currentResult = null;
    function TestComponent() {
      currentResult = hookFn();
      return null;
    }
    await act(async () => {
      root.render(<TestComponent />);
    });
    // Flush initial getCase promise
    await act(async () => {
      await Promise.resolve();
    });
    return {
      get current() {
        return currentResult;
      },
    };
  }

  test("TERMINAL_STATUSES contains all expected terminal states", () => {
    expect(TERMINAL_STATUSES.has("approved")).toBe(true);
    expect(TERMINAL_STATUSES.has("closed")).toBe(true);
    expect(TERMINAL_STATUSES.has("error")).toBe(true);
    expect(TERMINAL_STATUSES.has("options_ready")).toBe(true);
    expect(TERMINAL_STATUSES.has("investigating")).toBe(false);
    expect(TERMINAL_STATUSES.has("open")).toBe(false);
  });

  test("stops polling when case status is terminal (e.g. options_ready)", async () => {
    api.getCase.mockResolvedValue({ case_id: "case_001", status: "options_ready" });

    const result = await renderHookHelper(() => useCasePolling("case_001", 1000));

    expect(api.getCase).toHaveBeenCalledTimes(1);
    expect(result.current.caseData).toEqual({ case_id: "case_001", status: "options_ready" });

    // Advance timers significantly — no further polling should happen
    await act(async () => {
      jest.advanceTimersByTime(10000);
      await Promise.resolve();
    });

    expect(api.getCase).toHaveBeenCalledTimes(1);
  });

  test("stops polling on approved terminal state", async () => {
    api.getCase.mockResolvedValue({ case_id: "case_002", status: "approved" });

    const result = await renderHookHelper(() => useCasePolling("case_002", 1000));

    expect(api.getCase).toHaveBeenCalledTimes(1);
    expect(result.current.caseData?.status).toBe("approved");

    await act(async () => {
      jest.advanceTimersByTime(30000);
      await Promise.resolve();
    });

    expect(api.getCase).toHaveBeenCalledTimes(1);
  });

  test("polls and applies exponential backoff during non-terminal status (investigating)", async () => {
    api.getCase.mockResolvedValue({ case_id: "case_003", status: "investigating" });

    await renderHookHelper(() => useCasePolling("case_003", 1000, 15000, 2.0));

    // First call (immediate)
    expect(api.getCase).toHaveBeenCalledTimes(1);

    // After 1000ms: triggers second poll
    await act(async () => {
      jest.advanceTimersByTime(1000);
      await Promise.resolve();
    });
    expect(api.getCase).toHaveBeenCalledTimes(2);

    // Advance 1000ms: next interval is 2000ms, so it should not fire yet
    await act(async () => {
      jest.advanceTimersByTime(1000);
      await Promise.resolve();
    });
    expect(api.getCase).toHaveBeenCalledTimes(2);

    // Advance another 1000ms (total 2000ms): fires third call
    await act(async () => {
      jest.advanceTimersByTime(1000);
      await Promise.resolve();
    });
    expect(api.getCase).toHaveBeenCalledTimes(3);
  });

  test("stops polling when case transitions from investigating to options_ready", async () => {
    api.getCase
      .mockResolvedValueOnce({ case_id: "case_004", status: "investigating" })
      .mockResolvedValueOnce({ case_id: "case_004", status: "options_ready" });

    const result = await renderHookHelper(() => useCasePolling("case_004", 1000));

    expect(api.getCase).toHaveBeenCalledTimes(1);
    expect(result.current.caseData?.status).toBe("investigating");

    // Advance by initial interval to trigger 2nd poll
    await act(async () => {
      jest.advanceTimersByTime(1000);
      await Promise.resolve();
    });
    expect(api.getCase).toHaveBeenCalledTimes(2);
    expect(result.current.caseData?.status).toBe("options_ready");

    // Subsequent timers should not fire
    await act(async () => {
      jest.advanceTimersByTime(20000);
      await Promise.resolve();
    });
    expect(api.getCase).toHaveBeenCalledTimes(2);
  });
});

