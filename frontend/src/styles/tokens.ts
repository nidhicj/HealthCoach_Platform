// Motion constants for JavaScript-driven animation (rare).
// Source of truth: frontend/theme.yaml → scripts/build-theme.mjs
// CSS equivalents live in tokens.generated.css as --motion-* custom properties.
export const motion = {
  stateChange:    { durationMs: 150, easing: "ease-out" },
  reveal:         { durationMs: 200, easing: "ease-out" },
  sheetEnter:     { durationMs: 250, easing: "ease-out" },
  sheetExit:      { durationMs: 200, easing: "ease-in" },
  pageTransition: { durationMs: 300, easing: "ease-in-out" },
} as const;
