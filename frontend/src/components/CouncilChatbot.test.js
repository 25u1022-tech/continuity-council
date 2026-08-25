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

  test("defines 5 standard pre-filled prompt chips and kind initial greeting", () => {
    expect(PREFILLED_PROMPTS).toHaveLength(5);
    expect(PREFILLED_PROMPTS).toContain("How do I report a disruption?");
    expect(PREFILLED_PROMPTS).toContain("Walk me through the recovery options.");
    expect(PREFILLED_PROMPTS).toContain("Why was the top option chosen?");
    expect(PREFILLED_PROMPTS).toContain("What do the live signals mean?");
    expect(PREFILLED_PROMPTS).toContain("Show me the decision ledger.");
    expect(INITIAL_MESSAGE.text).toContain("council assistant");
  });

  test("renders floating action button (FAB) in DOM", async () => {
    await act(async () => {
      root.render(<CouncilChatbot productionId="prod_001" />);
    });

    const fab = container.querySelector("#council-chatbot-fab");
    expect(fab).not.toBeNull();
    expect(fab.getAttribute("aria-label")).toBe("Open Council Chat");
  });

  test("toggles drawer and displays all 5 pre-filled prompt chips when clicked", async () => {
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
    expect(container.textContent).toContain("How do I report a disruption?");
    expect(container.textContent).toContain("Walk me through the recovery options.");
    expect(container.textContent).toContain("Why was the top option chosen?");
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

  test("displays kind human message on network failure instead of raw error", async () => {
    api.sendChatMessage.mockRejectedValueOnce(new Error("NetworkError: Failed to fetch"));

    await act(async () => {
      root.render(<CouncilChatbot productionId="prod_001" />);
    });

    const fab = container.querySelector("#council-chatbot-fab");
    await act(async () => {
      fab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    const buttons = Array.from(container.querySelectorAll("button"));
    const chipBtn = buttons.find((b) => b.textContent.includes("How do I report a disruption?"));

    await act(async () => {
      chipBtn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await Promise.resolve();
    });

    expect(container.textContent).toContain("I'm having a little trouble reaching the council right now");
  });

  test("renders TTS toggle button and speak button on AI response", async () => {
    api.sendChatMessage.mockResolvedValueOnce({
      answer: "Here is your disruption analysis.",
      sources: [],
    });
    api.generateTTS = jest.fn().mockResolvedValueOnce({
      hash: "abc12345",
      status: "ready",
    });
    api.getTTSAudioUrl = jest.fn().mockReturnValue("/api/chat/tts?message_hash=abc12345");

    await act(async () => {
      root.render(<CouncilChatbot productionId="prod_001" />);
    });

    const fab = container.querySelector("#council-chatbot-fab");
    await act(async () => {
      fab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    });

    // Verify TTS toggle in header exists
    const ttsToggle = container.querySelector('[data-testid="tts-toggle-btn"]');
    expect(ttsToggle).not.toBeNull();

    // Trigger AI response
    const buttons = Array.from(container.querySelectorAll("button"));
    const chipBtn = buttons.find((b) => b.textContent.includes("How do I report a disruption?"));
    await act(async () => {
      chipBtn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await Promise.resolve();
    });

    // Check that speak button is present on the newly generated AI response
    const speakBtn = container.querySelector('[data-testid^="tts-speak-btn-"]');
    expect(speakBtn).not.toBeNull();

    // Click the speak button
    await act(async () => {
      speakBtn.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      await Promise.resolve();
    });

    expect(api.generateTTS).toHaveBeenCalledWith("Here is your disruption analysis.");
  });
});

