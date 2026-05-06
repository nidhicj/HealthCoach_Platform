# Parivarthan Frontend Brand Rules

**Read this skill before touching any frontend file in this repo.**
Source documents: `Poshini_Brand_Colour_Guide fina;.docx` + `docs/specs/Unit_001_HcCoreCycle/PHASE-06-frontend.md`

---

## §1 Palette rules

Four colours. Nothing else.

| Token | Hex | Tailwind class | Rule |
|---|---|---|---|
| Parchment | `#F7F4EE` | `bg-parchment` / `bg-background` | **Always the background base. Never swap for white.** |
| Moss Shadow | `#5C6652` | `bg-moss-shadow` / `bg-primary` | **Bounded blocks only** — headers, cards, sidebars, accent lines. Never full-bleed background. |
| Dark Ink | `#2C2C1E` | `text-dark-ink` / `text-foreground` | Body text everywhere. **At most one architectural fill** (background/block) per screen. |
| Marigold | `#E8C547` | `bg-marigold` / `bg-accent` | **At most one element per screen.** Reserved for the single keystone action (Send MOM, primary CTA, sign-in accent). Never on body text or headlines. Never a background colour. |

Functional colours (`--color-success`, `--color-warning`, `--color-error`) appear **only** for their named states — never for decoration.

**Linter assertions** (verified by `brand-rules.spec.ts`):
- Count of elements with `background-color: rgb(232, 197, 71)` (Marigold) must be 0 or 1 per route.
- No element may have `background-color: rgb(255, 255, 255)` (white).
- Count of elements with `background-color: rgb(44, 44, 30)` (Dark Ink) must be ≤ 1 per route.

---

## §2 Typography rules

**Two typefaces. No substitutions.**

### Fraunces — headlines
- Variable: `--font-fraunces` → CSS class `font-heading`
- Weight 900 (regular): all `h1`–`h3`, primary headlines, empty-state statement copy
- Weight 900 italic: one italic punch per headline — the final phrase only. Moss Shadow colour.
- Weight 700: secondary headlines (`h4`–`h6`), testimonial quotes, section openers
- Weight 700 italic: softer pull quotes, card quotes on Moss Shadow background

### Manrope — body
- Variable: `--font-manrope` → CSS class `font-sans`
- Weight 400: all body text, captions, form labels, supporting copy. **Minimum 13px on screen. Full Dark Ink opacity always.**
- Weight 700: eyebrow labels — all-caps, letter-spaced, Moss Shadow colour. Usage: `text-xs font-bold uppercase tracking-widest text-primary`
- Weight 800: loud callouts, short bold statements, numbers that need to shout

**Type scale for UI:**
```
Display headline  Fraunces 900    36–48px   Moss Shadow or Dark Ink
Italic punch      Fraunces 900i   same      Dark Ink only
Eyebrow label     Manrope 700     10–11px   all-caps, letter-spaced, Moss Shadow
Body copy         Manrope 400     13–15px   Dark Ink at full opacity
Bold callout      Manrope 800     13–14px   Dark Ink full opacity
Card quote        Fraunces 700i   13–15px   Parchment on Moss bg
```

---

## §3 Motion rules

Source: `frontend/theme.yaml` → `frontend/src/styles/tokens.generated.css` and `tokens.ts`

**Four primitives only:**

| Name | Duration | Easing | Applies to |
|---|---|---|---|
| `state_change` | 150ms | ease-out | hover/focus/click on buttons, links, inputs |
| `reveal` | 200ms | ease-out | dropdowns, tooltips, popovers |
| `sheet_enter` | 250ms | ease-out | Sheet and Dialog open |
| `sheet_exit` | 200ms | ease-in | Sheet and Dialog close |
| `page_transition` | 300ms | ease-in-out | route changes via View Transitions API |

**Animate only `transform` and `opacity`.** Never animate `width`, `height`, `top`, `left`, `padding`, `margin`, `border-width`, or `filter`.

**Hard ceiling: 400ms.** Any animation longer than 400ms is a violation.

**Banned:**
- Framer Motion (not installed, not needed at MVP)
- GIF or Lottie assets
- `backdrop-filter` outside the one app-bar (heavy on mobile Firefox)
- Scroll-triggered animations on more than one element per screen
- `<link rel="stylesheet">` to Google Fonts (always `next/font`)

---

## §4 shadcn token mapping

shadcn components use semantic tokens. **Never edit a file under `src/components/ui/` directly.** Wrap or extend instead (`src/components/wrapped/`).

| shadcn token | Brand value |
|---|---|
| `--background` | Parchment `#F7F4EE` |
| `--foreground` | Dark Ink `#2C2C1E` |
| `--primary` | Moss Shadow `#5C6652` |
| `--primary-foreground` | Parchment |
| `--accent` | Marigold `#E8C547` |
| `--accent-foreground` | Dark Ink |
| `--border` | Moss Shadow at 20% opacity |
| `--ring` | Moss Shadow |
| `--destructive` | Error `#A23E2E` |

Default `<Button>` → Moss Shadow (primary). Marigold lives only on `<Button variant="accent">`. Use it at most once per screen.

---

## §5 Per-screen checklist

Run this before claiming any screen done:

- [ ] Body text uses Manrope (font-sans), headlines use Fraunces (font-heading)
- [ ] At most **one Marigold element** on this screen — which one is it?
- [ ] At most **one Dark Ink architectural fill** (background/block) on this screen
- [ ] **No `bg-white`**, **no `#FFFFFF`**, **no `bg-[#ffffff]`** anywhere in this screen's tree
- [ ] All CSS transitions are ≤ 400ms and animate only `transform` / `opacity`
- [ ] Mobile 375px viewport: no horizontal scroll, no clipped text
- [ ] Desktop 1280px viewport: layout holds, no overflow
- [ ] `npm run build` passes with no type errors on this screen
- [ ] Playwright brand-rules spec passes on this route in Chromium and Firefox

---

## §6 When in doubt

- Reach for **Moss Shadow**, not Dark Ink.
- Reach for **paragraph**, not heading.
- Reach for **plain text**, not a graphic or icon block.
- Add Marigold **only** if you can name the single most important user action on this screen.
- Tokens come from `theme.yaml` only — **never hand-edit hex values in components or globals.css**.

---

## §7 Banned patterns (enforced by linter or self-check)

```
bg-white                   # Parchment is the base
bg-[#ffffff]               # same
text-white                 # only on Moss Shadow or Dark Ink surfaces
any hex literal in JSX     # all colours via Tailwind tokens only
httpx.AsyncClient(         # backend convention, not applicable to frontend
localStorage token         # ADR-0005: access token in memory only
sessionStorage token       # same
fetch() in a component     # always via src/lib/api/ wrappers
```
