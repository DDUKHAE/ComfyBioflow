# ComfyBIO Panel — ComfyUI-Native Restyle Design

**Date:** 2026-07-10
**Status:** Approved (brainstorming)
**Scope:** CSS-only restyle of the ComfyBIO floating panel to match the ComfyUI environment. No structural, layout, logic, or API changes.

## Problem

The current panel (`web/js/comfybio_panel.js`, `injectStyles()`) paints its own hardcoded dark palette that reads as "cyber" and clashes with the surrounding ComfyUI UI. Four root causes:

1. **Neon teal accent** (`#20b2aa`) plus teal-tinted glow shadows.
2. **Hardcoded colors** (`#1c1c1c`, `#252525`, `#1d2228`, `#222629`, …) that stay dark regardless of the user's ComfyUI theme.
3. **Forced Inter font**, different from the ComfyUI host typeface.
4. **Oversized glow shadows** — round glowing launcher (`0 16px 34px`) and heavy panel shadow (`0 24px 60px`).

## Goal

Make the panel visually indistinguishable-in-spirit from native ComfyUI chrome by adopting the CSS custom properties ComfyUI already exposes, so the panel inherits the active theme (including light mode, which currently breaks). Keep the floating draggable/resizable form factor — only the look changes.

## Approach

CSS-only refactor confined to `injectStyles()` in `web/js/comfybio_panel.js`. The panel HTML structure (`createPanel`, `createStep`, resource builders) and all behavior in `initializePanel` remain **byte-for-byte unchanged** except where a color literal is embedded in an `innerHTML` template (none currently are — all colors live in the stylesheet, confirmed by read).

### Confirmed ComfyUI variables

Verified present in the installed `comfyui_frontend_package` bundle (usage counts):

- `--comfy-menu-bg` (70) — primary panel/menu background
- `--comfy-menu-secondary-bg` (3) — nested section / popover background
- `--comfy-input-bg` (21) — input field background
- `--border-color` (30)
- `--fg-color` (29) — foreground text
- `--descrip-text` (38) — muted/description text
- `--input-text` (33)
- `--content-bg` (6) / `--content-fg` (3)
- `--p-primary-color` (20) — PrimeVue primary accent
- `--p-primary-contrast-color` — accent-on text (PrimeVue standard)
- `--p-form-field-border-color` (9)

### Variable mapping

Every `--cb-*` token keeps its name (so no downstream selector churn) but its value becomes a `var(--comfy-token, <existing-literal>)` with the current hardcoded value as fallback, so older ComfyUI builds without the variable degrade gracefully to today's appearance.

| `--cb-*` token (role) | New value |
|---|---|
| `--cb-bg` (inset input bg) | `var(--comfy-input-bg, #1c1c1c)` |
| `--cb-panel` (panel bg) | `var(--comfy-menu-bg, #252525)` |
| `--cb-panel-2` (section bg) | `var(--comfy-menu-secondary-bg, #2f2f2f)` |
| `--cb-line` (borders) | `var(--border-color, #454545)` |
| `--cb-text` (text) | `var(--fg-color, #f1f1f1)` |
| `--cb-muted` (muted text) | `var(--descrip-text, #a8a8a8)` |
| `--cb-soft` (secondary text) | `var(--fg-color, #d6d6d6)` |
| `--cb-teal` → renamed `--cb-accent` (accent) | `var(--p-primary-color, #20b2aa)` |
| `--cb-accent-contrast` (new, accent-on text) | `var(--p-primary-contrast-color, #081013)` |

Hardcoded popover/message backgrounds embedded directly in selectors (`#1d2228`, `#222629`, `rgba(37,37,37,.96)`) are replaced with `var(--comfy-menu-secondary-bg, …)` / `var(--comfy-menu-bg, …)` carrying their current literal as fallback.

### Status colors (semantic — retained)

`--cb-green` (success) and `--cb-amber` (warning) carry *meaning* (e.g. "Spec valid" badge, review-required chips), not decoration, so they are kept — renamed to `--cb-success` / `--cb-warning` for clarity and slightly desaturated. They are NOT mapped to the ComfyUI accent. All references (`.cb-status`, `.cb-chip`, `.cb-chip.amber`, `.cb-message .severity`, `--cb-green`/`--cb-amber` usages) update to the new names.

### Accent application

All teal usages route through `--cb-accent`:
- `.cb-button.apply` background = `--cb-accent`, text = `--cb-accent-contrast`.
- Active tab (`.cb-tab.active`), badge (`.cb-badge`), replace-option recommended border, `.cb-message` left border, path/add-step menu borders, expanded-step border.

### Launcher restyle

- Background `#183331` → `var(--comfy-menu-bg, …)`; border `rgba(32,178,170,.65)` → `var(--border-color, …)`.
- Glow shadow `0 16px 34px rgba(0,0,0,.3)` → subtle `0 2px 8px rgba(0,0,0,.35)`.
- `panel-open` state background `#2b3037` → `var(--comfy-menu-secondary-bg, …)`.
- **DNA SVG icon kept**; its `color` becomes `var(--p-primary-color, …)`.

### Other tidying

- **Font:** remove the `font-family: Inter, …` declaration from `.comfybio-launcher, .comfybio-panel, .comfybio-panel *` so text inherits the ComfyUI host font. Keep `box-sizing` and `letter-spacing: 0`.
- **Panel shadow:** `0 24px 60px rgba(0,0,0,.36)` → `0 8px 24px rgba(0,0,0,.3)`.
- **Scrollbars:** remove the `scrollbar-width: none` / `::-webkit-scrollbar { display:none }` rules so the panel shows the same thin native scrollbars as the rest of ComfyUI.

## Out of scope (YAGNI)

- Sidebar docking / `registerSidebarTab` migration — floating form retained.
- Any change to tabs, layout, fields, or step/resource structure.
- Any change to JS behavior, event handlers, or the `/comfybio/*` API calls.

## Testing / Verification

No automated tests cover panel CSS (it is injected DOM styling). Verification is manual:

1. Restart ComfyUI; open the panel — confirm it reads as native ComfyUI chrome in the default dark theme (no neon teal, no glow).
2. Switch the ComfyUI theme to light — confirm the panel adapts automatically (backgrounds, text, borders all legible), which the current hardcoded build fails.
3. Regression-check interaction: launcher drag + open/close, panel resize (all 8 handles), tab switching, step expand/drag-reorder/remove/replace, resource add/remove/browse, submit/generate calls — all must behave exactly as before (styling-only change).
4. Confirm success (green) and warning (amber) status indicators still render with their semantic colors.

## Risk / Rollback

Low risk: every variable carries its current literal as a `var()` fallback, so the worst case (ComfyUI exposes none of the expected variables) reproduces today's exact appearance. Rollback is reverting the single `injectStyles()` change.
