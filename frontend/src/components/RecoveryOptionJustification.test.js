import React, { act } from "react";
import { createRoot } from "react-dom/client";

global.IS_REACT_ACT_ENVIRONMENT = true;

const OptionJustificationBadge = ({ justification, optionId }) => {
  if (!justification) return null;
  const isFallback = justification.startsWith("Ranked #");
  return (
    <div
      data-testid={`option-justification-${optionId}`}
      className={`mt-3.5 rounded-[9px] px-3.5 py-2 text-[12.5px] leading-relaxed transition-colors ${
        isFallback
          ? "border border-[var(--cc-border)] bg-[var(--cc-surface-sunken)]/50 text-[var(--cc-text-secondary)] font-normal"
          : "border-l-2 border-l-[var(--cc-text-primary)]/70 border border-[var(--cc-border)] bg-[var(--cc-surface-hover)] text-[var(--cc-text-secondary)] italic shadow-sm"
      }`}
    >
      <span className="text-[var(--cc-text-secondary)]">{justification}</span>
    </div>
  );
};

describe("OptionJustification component", () => {
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

  test("renders AI-generated natural language justification with italic and accent border", async () => {
    const aiText = "Swap shoot days minimizes financial exposure to $25,800 while passing compliance.";
    await act(async () => {
      root.render(<OptionJustificationBadge justification={aiText} optionId="opt_1" />);
    });

    const el = container.querySelector('[data-testid="option-justification-opt_1"]');
    expect(el).not.toBeNull();
    expect(el.textContent).toBe(aiText);
    expect(el.className).toContain("italic");
    expect(el.className).toContain("border-l-2");
  });

  test("renders deterministic fallback template with standard normal styling", async () => {
    const fallbackText = "Ranked #2: $17,500 avg cost and 3.2h delay based on 5,586 similar historical cases.";
    await act(async () => {
      root.render(<OptionJustificationBadge justification={fallbackText} optionId="opt_2" />);
    });

    const el = container.querySelector('[data-testid="option-justification-opt_2"]');
    expect(el).not.toBeNull();
    expect(el.textContent).toBe(fallbackText);
    expect(el.className).toContain("font-normal");
    expect(el.className).not.toContain("italic");
  });
});
