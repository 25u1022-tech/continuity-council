/**
 * Continuity Council — Apple Minimal Design System Tokens
 * Exported token constants for programmatic use.
 */

export const tokens = {
  typography: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", "Segoe UI", Roboto, sans-serif',
    monoFamily: '"SF Mono", "IBM Plex Mono", Menlo, Monaco, Consolas, monospace',
    scale: {
      xs: "12px",
      sm: "13px",
      base: "15px",
      lg: "17px",
      xl: "20px",
      "2xl": "24px",
      "3xl": "30px",
    },
    weights: {
      regular: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
  },
  spacing: {
    1: "4px",
    2: "8px",
    3: "12px",
    4: "16px",
    6: "24px",
    8: "32px",
    12: "48px",
  },
  radii: {
    sm: "6px",
    md: "10px",
    lg: "14px",
    xl: "18px",
    full: "9999px",
  },
  transitions: {
    default: "all 200ms cubic-bezier(0.2, 0, 0, 1)",
    fast: "all 150ms cubic-bezier(0.2, 0, 0, 1)",
  },
};

export default tokens;
