/**
 * Safe localStorage and window/browser API utilities with fallbacks and null-safety.
 * Prevents throwing errors during render if localStorage/matchMedia is blocked or throws.
 */

export const safeStorage = {
  getItem: (key, defaultValue = null) => {
    try {
      if (typeof window === "undefined" || !window.localStorage) return defaultValue;
      const val = window.localStorage.getItem(key);
      return val !== null && val !== undefined ? val : defaultValue;
    } catch {
      return defaultValue;
    }
  },
  setItem: (key, value) => {
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        window.localStorage.setItem(key, String(value));
      }
    } catch {
      // Storage access blocked or quota exceeded
    }
  },
  removeItem: (key) => {
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        window.localStorage.removeItem(key);
      }
    } catch {
      // Storage access blocked
    }
  },
};

export const safeMatchMedia = (query) => {
  try {
    if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
      return window.matchMedia(query);
    }
  } catch {
    // matchMedia not supported or throws in sandbox
  }
  return {
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  };
};
