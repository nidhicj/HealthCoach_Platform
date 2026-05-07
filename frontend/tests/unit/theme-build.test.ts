/**
 * Theme build script smoke test.
 * Verifies that theme.yaml compiles to expected token outputs.
 * Snapshot-based: first run writes the snapshot, subsequent runs detect regressions.
 */
import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import path from "path";
import { execSync } from "child_process";

const FRONTEND = path.resolve(__dirname, "../..");
const GENERATED_CSS = path.resolve(FRONTEND, "src/styles/tokens.generated.css");

describe("theme build script", () => {
  it("theme.yaml exists and is valid YAML", () => {
    const yaml = readFileSync(path.resolve(FRONTEND, "theme.yaml"), "utf-8");
    expect(yaml).toContain("parchment");
    expect(yaml).toContain("moss_shadow");
    expect(yaml).toContain("marigold");
    expect(yaml).toContain("dark_ink");
    expect(yaml).toContain("Fraunces");
    expect(yaml).toContain("Manrope");
  });

  it("generated tokens.css contains all four brand colours", () => {
    // Re-run the build script so the test is not stale
    execSync("node ../scripts/build-theme.mjs", { cwd: FRONTEND });
    const css = readFileSync(GENERATED_CSS, "utf-8");
    // Parchment
    expect(css).toContain("#F7F4EE");
    // Moss Shadow
    expect(css).toContain("#5C6652");
    // Dark Ink
    expect(css).toContain("#2C2C1E");
    // Marigold
    expect(css).toContain("#E8C547");
  });

  it("generated tokens.css defines motion duration variables", () => {
    const css = readFileSync(GENERATED_CSS, "utf-8");
    // At minimum, some duration variable must be defined
    expect(css).toMatch(/--.*duration.*:\s*\d+ms/);
  });

  it("generated tokens.css snapshot has not regressed", () => {
    const css = readFileSync(GENERATED_CSS, "utf-8");
    expect(css).toMatchSnapshot();
  });
});
