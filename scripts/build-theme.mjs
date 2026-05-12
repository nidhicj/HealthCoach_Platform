#!/usr/bin/env node
/**
 * Reads frontend/theme.yaml and emits:
 *   frontend/src/styles/tokens.generated.css  — Tailwind v4 @theme block + CSS variables
 *
 * Run: node scripts/build-theme.mjs
 * Wired into: npm run predev + npm run prebuild in frontend/package.json
 */
import { readFileSync, writeFileSync, mkdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

// --- parse YAML manually (no deps — theme.yaml is simple enough) ---
function stripComment(line) {
  // Remove trailing # comment but preserve quoted values (e.g. "#F7F4EE")
  // Strategy: find # that is preceded by whitespace (not inside quotes)
  let inQuote = false;
  let quoteChar = null;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (!inQuote && (ch === '"' || ch === "'")) { inQuote = true; quoteChar = ch; }
    else if (inQuote && ch === quoteChar) { inQuote = false; quoteChar = null; }
    else if (!inQuote && ch === '#') { return line.slice(0, i).trimEnd(); }
  }
  return line.trimEnd();
}

function parseTheme(raw) {
  const lines = raw.split("\n");
  const theme = { palette: { functional: {} }, fonts: {}, motion: {}, spacing: {}, radii: {} };
  let section = null;
  let subSection = null;

  for (const line of lines) {
    const stripped = stripComment(line);
    if (!stripped.trim()) continue;

    const indent = stripped.match(/^(\s*)/)[1].length;
    const kv = stripped.trim().match(/^([^:]+):\s*(.*)$/);
    if (!kv) continue;
    const [, key, val] = kv;
    const clean = val.replace(/["']/g, "").trim();

    if (indent === 0) { section = key; subSection = null; continue; }
    if (indent === 2 && section === "palette" && key === "functional") { subSection = "functional"; continue; }

    if (section === "palette") {
      if (subSection === "functional") theme.palette.functional[key] = clean;
      else theme.palette[key] = clean;
    } else if (section === "motion") {
      const m = val.match(/duration_ms:\s*(\d+).*easing:\s*["']?([^"',}]+)/);
      if (m) theme.motion[key] = { duration_ms: parseInt(m[1]), easing: m[2].trim() };
    } else if (section === "spacing") {
      theme.spacing[key] = parseInt(clean);
    } else if (section === "radii") {
      theme.radii[key] = parseInt(clean);
    }
  }
  return theme;
}

const raw = readFileSync(join(root, "frontend/theme.yaml"), "utf8");
const theme = parseTheme(raw);

// --- build CSS ---
const p = theme.palette;
const m = theme.motion;
const s = theme.spacing;
const r = theme.radii;

const css = `/* AUTO-GENERATED — do not edit. Source: frontend/theme.yaml */
/* Run: node scripts/build-theme.mjs */

@theme {
  /* Brand palette */
  --color-parchment:    ${p.parchment};
  --color-moss-shadow:  ${p.moss_shadow};
  --color-dark-ink:     ${p.dark_ink};
  --color-marigold:     ${p.marigold};
  --color-section-fill-01: ${p.section_fill_01};
  --color-section-fill-02: ${p.section_fill_02};

  /* Functional colours — never decorative */
  --color-success: ${p.functional.success};
  --color-warning: ${p.functional.warning};
  --color-error:   ${p.functional.error};

  /* Spacing scale (4pt) */
  --spacing-tight:   ${s.tight}px;
  --spacing-loose:   ${s.loose}px;
  --spacing-regular: ${s.regular}px;
  --spacing-section: ${s.section}px;
  --spacing-page:    ${s.page}px;

  /* Border radii */
  --radius-sm: ${r.sm}px;
  --radius-md: ${r.md}px;
  --radius-lg: ${r.lg}px;
}

/* Motion durations as plain CSS custom properties (used by motion.ts and motion.css) */
:root {
  --motion-state-change-duration:    ${m.state_change.duration_ms}ms;
  --motion-state-change-easing:      ${m.state_change.easing};
  --motion-reveal-duration:          ${m.reveal.duration_ms}ms;
  --motion-reveal-easing:            ${m.reveal.easing};
  --motion-sheet-enter-duration:     ${m.sheet_enter.duration_ms}ms;
  --motion-sheet-enter-easing:       ${m.sheet_enter.easing};
  --motion-sheet-exit-duration:      ${m.sheet_exit.duration_ms}ms;
  --motion-sheet-exit-easing:        ${m.sheet_exit.easing};
  --motion-page-transition-duration: ${m.page_transition.duration_ms}ms;
  --motion-page-transition-easing:   ${m.page_transition.easing};
}
`;

const outDir = join(root, "frontend/src/styles");
mkdirSync(outDir, { recursive: true });
writeFileSync(join(outDir, "tokens.generated.css"), css, "utf8");

console.log("✓ frontend/src/styles/tokens.generated.css written");
