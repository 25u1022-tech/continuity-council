import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { CouncilChatbot, PREFILLED_PROMPTS, INITIAL_MESSAGE } from "./CouncilChatbot";
import * as api from "../lib/api";

global.IS_REACT_ACT_ENVIRONMENT = true;
jest.mock("../lib/api");

describe("CouncilChatbot Component", () => {
  let container = null;
  let root = null;

  beforeEach(() => {
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
  });

  test("defines 3 standard pre-filled prompt chips and initial greeting", () => {
    expect(PREFILLED_PROMPTS).toHaveLength(3);
    expect(PREFILLED_PROMPTS).toContain("Why was the top option chosen?");
    expect(PREFILLED_PROMPTS).toContain("Show me historical weather disruptions for this location.");
    expect(PREFILLED_PROMPTS).toContain("What evidence supports Option A?");
    expect(INITIAL_MESSAGE.text).toContain("Continuity Council's reasoning interface");
  });

  test("renders floating action button (FAB) in DOM", async () => {
    await act(async () => {
      root.render(<CouncilChatbot productionId="prod_001" />);
    });

    const fab = container.querySelector("#council-chatbot-fab");
    expect(fab).not.toBeNull();
    expect(fab.getAttribute("aria-label")).toBe("Open Council Chat");
  });

  test("toggles drawer and displays pre-filled prompt chips when clicked", async () => {
    await act(async () => {
      root.render(<CouncilChatbot productionId="prod_001" />);
    });

    const fab = container.querySelector("#council-chatbot-fab");
    await act(async () => {
      fab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(container.textContent).toContain("Council Reasoning");
    expect(container.textContent).toContain("Why was the top option chosen?");
    expect(container.textContent).toContain("Show me historical weather disruptions for this location.");
  });

  test("clicking prompt chip triggers sendChatMessage and displays response", async () => {
    api.sendChatMessage.mockResolvedValueOnce({
      answer: "Option Shoot Cover Scenes was chosen based on ClickHouse evidence.",
      sources: [
        {
          type: "mcp_query",
          query: "SELECT * FROM strategy_performance_mv",
          result_summary: "Past cases n=200",
        },
      ],
    });

    await act(async () => {
      root.render(<CouncilChatbot productionId="prod_001" caseId="case_123" />);
    });

    const fab = container.querySelector("#council-chatbot-fab");
    await act(async () => {
      fab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    // Find and click the prompt chip button
    const buttons = Array.from(container.querySelectorAll("button"));
    const chipBtn = buttons.find((b) => b.textContent.includes("Why was the top option chosen?"));
    expect(chipBtn).toBeDefined();

    await act(async () => {
      chipBtn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      // Allow async API promise to resolve
      await Promise.resolve();
    });

    expect(api.sendChatMessage).toHaveBeenCalledWith({
      message: "Why was the top option chosen?",
      production_id: "prod_001",
      case_id: "case_123",
    });

    expect(container.textContent).toContain("Option Shoot Cover Scenes was chosen");
    expect(container.textContent).toContain("ClickHouse Evidence Sources:");
    expect(container.textContent).toContain("MCP Query");
  });
});
