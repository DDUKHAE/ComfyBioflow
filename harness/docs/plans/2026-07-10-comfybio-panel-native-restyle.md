# ComfyBIO Panel Native-Restyle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the ComfyBIO floating panel to inherit the ComfyUI theme (dark and light) by replacing hardcoded colors, neon-teal accents, glow shadows, and the forced Inter font with ComfyUI's exposed CSS variables — with zero structural, layout, logic, or API changes.

**Architecture:** Every change is confined to the `injectStyles()` template string in `web/js/comfybio_panel.js`. The `:root` design tokens become `var(--comfy-token, <old-literal>)` with the current value as a graceful fallback; the neon accent maps to `--p-primary-color`; tinted borders/backgrounds use `color-mix()` over the themed accent/status tokens. All panel HTML and all `initializePanel` behavior stay byte-for-byte unchanged.

**Tech Stack:** Vanilla JS + injected CSS (no build step, no framework). `color-mix(in srgb, …)` — supported in the modern Chromium the ComfyUI frontend targets (Chrome 111+, 2023).

## Global Constraints

- **Single file only:** all edits are inside `web/js/comfybio_panel.js`, within the `injectStyles()` stylesheet template. Touch nothing else.
- **No behavior change:** do not edit any HTML template (`createPanel`, `createStep`, resource builders) or any handler in `initializePanel`. Styling only.
- **Fallbacks mandatory:** every ComfyUI variable reference keeps the current literal as a `var(--comfy-token, <literal>)` fallback so older ComfyUI builds render as they do today.
- **Semantic status colors retained:** success (green `#41c287`) and warning (amber `#e8b04e`) carry meaning and are kept (renamed `--cb-success` / `--cb-warning`), NOT mapped to the accent.
- **No new tests:** panel CSS has no automated test surface. Per-task verification is `grep` assertions over the file; final validation is manual in ComfyUI (see Manual Verification section).
- **Commit identity:** commit as `ddukhae <dongjoon69@gmail.com>` (use `git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com`). End commit messages with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.

---

### Task 1: Theme tokens, accent rename, and font

**Files:**
- Modify: `web/js/comfybio_panel.js` (the `:root` block ~line 108, the shared `font-family` rule ~line 122, and the 10 solid accent/status references listed below)

**Interfaces:**
- Produces: CSS custom properties `--cb-accent`, `--cb-accent-contrast`, `--cb-success`, `--cb-warning` (replacing `--cb-teal`, `--cb-green`, `--cb-amber`); themed `--cb-bg/panel/panel-2/line/text/muted/soft`. Tasks 2 and 3 consume `--cb-accent`, `--cb-success`, `--cb-warning`.

- [ ] **Step 1: Replace the `:root` token block**

Find:
```css
    :root {
      --cb-bg: #1c1c1c;
      --cb-panel: #252525;
      --cb-panel-2: #2f2f2f;
      --cb-line: #454545;
      --cb-text: #f1f1f1;
      --cb-muted: #a8a8a8;
      --cb-soft: #d6d6d6;
      --cb-teal: #20b2aa;
      --cb-green: #41c287;
      --cb-amber: #e8b04e;
    }
```
Replace with:
```css
    :root {
      --cb-bg: var(--comfy-input-bg, #1c1c1c);
      --cb-panel: var(--comfy-menu-bg, #252525);
      --cb-panel-2: var(--comfy-menu-secondary-bg, #2f2f2f);
      --cb-line: var(--border-color, #454545);
      --cb-text: var(--fg-color, #f1f1f1);
      --cb-muted: var(--descrip-text, #a8a8a8);
      --cb-soft: var(--fg-color, #d6d6d6);
      --cb-accent: var(--p-primary-color, #20b2aa);
      --cb-accent-contrast: var(--p-primary-contrast-color, #081013);
      --cb-success: #41c287;
      --cb-warning: #e8b04e;
    }
```

- [ ] **Step 2: Remove the forced Inter font**

Find:
```css
    .comfybio-launcher, .comfybio-panel, .comfybio-panel * {
      box-sizing: border-box;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
```
Replace with:
```css
    .comfybio-launcher, .comfybio-panel, .comfybio-panel * {
      box-sizing: border-box;
      letter-spacing: 0;
    }
```

- [ ] **Step 3: Rename the 6 solid `var(--cb-teal)` accent references**

Use Edit with `replace_all: true` for the repeated string `      color: var(--cb-teal);` → `      color: var(--cb-accent);` (occurs 3×: launcher svg, `.cb-message .severity`, `.cb-badge`).

Then three unique single edits:
- `      background: var(--cb-teal);` → `      background: var(--cb-accent);`
- `      border-color: var(--cb-teal);` → `      border-color: var(--cb-accent);`
- `      border-left: 3px solid var(--cb-teal);` → `      border-left: 3px solid var(--cb-accent);`

- [ ] **Step 4: Route the apply-button text color to the accent-contrast token**

Find `      color: #081013;` → replace with `      color: var(--cb-accent-contrast);`

- [ ] **Step 5: Rename the solid status-color references**

- `      color: var(--cb-green);` → `      color: var(--cb-success);` (Edit with `replace_all: true`; occurs 2×: `.cb-status`, `.cb-chip`)
- `      color: var(--cb-amber);` → `      color: var(--cb-warning);` (single: `.cb-chip.amber`)

- [ ] **Step 6: Verify no stale token names or literals remain**

Run:
```bash
cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow
grep -nE "var\(--cb-(teal|green|amber)\)" web/js/comfybio_panel.js; echo "stale-refs-exit:$?"
grep -n "font-family: Inter" web/js/comfybio_panel.js; echo "inter-exit:$?"
grep -n "#081013;" web/js/comfybio_panel.js; echo "literal081013-exit:$?"
grep -cE "^\s+--cb-(accent|accent-contrast|success|warning):" web/js/comfybio_panel.js
```
Expected: first three greps print nothing and report `...-exit:1` (no match); the final `grep -c` prints `4`.

- [ ] **Step 7: Commit**

```bash
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com add web/js/comfybio_panel.js
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "style: theme ComfyBIO panel tokens to ComfyUI variables

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Accent and status tints via color-mix

**Files:**
- Modify: `web/js/comfybio_panel.js` (13 tinted `rgba(...)` literals for active/recommended/status affordances)

**Interfaces:**
- Consumes: `--cb-accent`, `--cb-success`, `--cb-warning` from Task 1.
- Produces: no new tokens; converts translucent tints to theme-following `color-mix()`.

Note: the launcher border tint `rgba(32, 178, 170, 0.65)` is intentionally NOT converted here — it becomes `var(--cb-line)` in Task 3. After this task exactly one `rgba(32, 178, 170` literal (the launcher border) remains.

- [ ] **Step 1: Convert the 8 accent tints**

Apply these unique single edits (alpha → percentage):
- `      border-color: rgba(32, 178, 170, 0.7);` → `      border-color: color-mix(in srgb, var(--cb-accent) 70%, transparent);`
- `      background: rgba(32, 178, 170, 0.14);` → `      background: color-mix(in srgb, var(--cb-accent) 14%, transparent);`
- `      border: 1px solid rgba(32, 178, 170, 0.48);` → `      border: 1px solid color-mix(in srgb, var(--cb-accent) 48%, transparent);`
- `      border-color: rgba(32, 178, 170, 0.58);` → `      border-color: color-mix(in srgb, var(--cb-accent) 58%, transparent);`
- `      border: 1px solid rgba(32, 178, 170, .45);` → `      border: 1px solid color-mix(in srgb, var(--cb-accent) 45%, transparent);`
- `      border: 1px solid rgba(32, 178, 170, .48);` → `      border: 1px solid color-mix(in srgb, var(--cb-accent) 48%, transparent);`
- `      border-color: rgba(32, 178, 170, .72);` → `      border-color: color-mix(in srgb, var(--cb-accent) 72%, transparent);`
- `      background: rgba(32, 178, 170, .1);` → `      background: color-mix(in srgb, var(--cb-accent) 10%, transparent);`

- [ ] **Step 2: Convert the 4 success tints and 1 warning tint**

- `      border: 1px solid rgba(65, 194, 135, 0.45);` → `      border: 1px solid color-mix(in srgb, var(--cb-success) 45%, transparent);`
- `      background: rgba(65, 194, 135, 0.08);` → `      background: color-mix(in srgb, var(--cb-success) 8%, transparent);`
- `      border: 1px solid rgba(65, 194, 135, .45);` → `      border: 1px solid color-mix(in srgb, var(--cb-success) 45%, transparent);`
- `      background: rgba(65, 194, 135, .08);` → `      background: color-mix(in srgb, var(--cb-success) 8%, transparent);`
- `      border-color: rgba(232, 176, 78, .45);` → `      border-color: color-mix(in srgb, var(--cb-warning) 45%, transparent);`

- [ ] **Step 3: Verify tint conversions**

Run:
```bash
cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow
echo "accent-tints-left: $(grep -cE 'rgba\(32, ?178, ?170' web/js/comfybio_panel.js)"   # expect 1 (launcher border)
echo "success-tints-left: $(grep -cE 'rgba\(65, ?194, ?135' web/js/comfybio_panel.js)"   # expect 0
echo "warning-tints-left: $(grep -cE 'rgba\(232, ?176, ?78' web/js/comfybio_panel.js)"   # expect 0
echo "color-mix-count: $(grep -c 'color-mix' web/js/comfybio_panel.js)"                    # expect 13
```
Expected: `accent-tints-left: 1`, `success-tints-left: 0`, `warning-tints-left: 0`, `color-mix-count: 13`.

- [ ] **Step 4: Commit**

```bash
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com add web/js/comfybio_panel.js
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "style: convert panel tints to theme-following color-mix

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Launcher, surfaces, shadows, and native scrollbars

**Files:**
- Modify: `web/js/comfybio_panel.js` (launcher block, panel shadow, scrollbar-hiding rules, hardcoded popover/message/footer backgrounds)

**Interfaces:**
- Consumes: `--cb-panel`, `--cb-panel-2`, `--cb-line` from Task 1.
- Produces: final themed surfaces; no new tokens.

- [ ] **Step 1: Retheme the launcher button**

- `      border: 1px solid rgba(32, 178, 170, 0.65);` → `      border: 1px solid var(--cb-line);`
- `      background: #183331;` → `      background: var(--cb-panel);`
- `      box-shadow: 0 16px 34px rgba(0, 0, 0, 0.3);` → `      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);`
- `      background: #2b3037;` → `      background: var(--cb-panel-2);` (the `.panel-open` state)

- [ ] **Step 2: Soften the panel shadow**

Find `      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.36);` → replace with `      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);`

- [ ] **Step 3: Remove the scrollbar-hiding rules so native ComfyUI scrollbars show**

Find:
```css
    .comfybio-panel,
    .comfybio-panel * {
      scrollbar-width: none;
      -ms-overflow-style: none;
    }

    .comfybio-panel::-webkit-scrollbar,
    .comfybio-panel *::-webkit-scrollbar {
      display: none;
    }

```
Replace with an empty string (delete the whole block, including its trailing blank line).

- [ ] **Step 4: Retheme hardcoded popover / message / footer backgrounds**

- `      background: #1d2228;` → `      background: var(--cb-panel-2);` (Edit with `replace_all: true`; occurs 2×: `.cb-path-menu`/`.cb-add-step-menu` and `.cb-replace-popover`)
- `      background: #222629;` → `      background: var(--cb-panel-2);` (single: `.cb-message`)
- `      background: rgba(37, 37, 37, .96);` → `      background: var(--cb-panel);` (single: `.cb-footer`)

- [ ] **Step 5: Verify all hardcoded surfaces and scrollbar rules are gone**

Run:
```bash
cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow
echo "accent-rgba-left: $(grep -cE 'rgba\(32, ?178, ?170' web/js/comfybio_panel.js)"   # expect 0
grep -nE "#183331|#2b3037|#1d2228|#222629|rgba\(37, ?37, ?37" web/js/comfybio_panel.js; echo "hardcoded-bg-exit:$?"
grep -n "scrollbar-width: none" web/js/comfybio_panel.js; echo "scrollbar-exit:$?"
grep -n "0 24px 60px" web/js/comfybio_panel.js; echo "panelshadow-exit:$?"
```
Expected: `accent-rgba-left: 0`; the three greps print nothing and report exit `1`.

- [ ] **Step 6: Confirm only intended neon literals survive (as fallbacks)**

Run:
```bash
cd /home/ydj/main/ComfyUI/custom_nodes/ComfyBioflow
echo "20b2aa: $(grep -c '#20b2aa' web/js/comfybio_panel.js)"   # expect 1 (--cb-accent fallback)
echo "081013: $(grep -c '#081013' web/js/comfybio_panel.js)"   # expect 1 (--cb-accent-contrast fallback)
echo "41c287: $(grep -c '#41c287' web/js/comfybio_panel.js)"   # expect 1 (--cb-success def)
echo "e8b04e: $(grep -c '#e8b04e' web/js/comfybio_panel.js)"   # expect 1 (--cb-warning def)
```
Expected: each prints `1`. Any higher count means a literal was missed.

- [ ] **Step 7: Commit**

```bash
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com add web/js/comfybio_panel.js
git -c user.name=ddukhae -c user.email=dongjoon69@gmail.com commit -m "style: theme launcher, surfaces, shadows; restore native scrollbars

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Manual Verification (human, in ComfyUI)

Not automatable in-session — the injected panel CSS only renders inside a running ComfyUI. After Task 3, the user performs:

1. Restart ComfyUI (or hard-reload the browser) and open the ComfyBIO panel via the launcher. Confirm it reads as native ComfyUI chrome in the default dark theme — no neon teal, no glow halo on the launcher, host font in use.
2. Switch the ComfyUI theme to light. Confirm the panel adapts automatically: backgrounds, text, borders, inputs all legible (this is the case the old hardcoded-dark build failed).
3. Regression-check interaction (styling-only change, so all must behave exactly as before): launcher drag + open/close, panel resize on all 8 handles, tab switching (Prompt / Tool Select / Generate Graph), step expand / drag-reorder / remove / replace, resource add / remove / Browse menu, Submit and Generate Graph requests.
4. Confirm the "Spec valid" status badge still renders green and review/warning chips still render amber (semantic status colors retained).

## Notes / Risk

- **color-mix support:** requires Chromium 111+ / the modern ComfyUI frontend; acceptable for this target. If a much older browser must be supported, the fallback is solid `var(--cb-accent)` borders without tint — not needed now.
- **Rollback:** every token carries its old literal as a `var()` fallback, so the worst case (no ComfyUI variables present) reproduces today's exact look. Full rollback is reverting the three commits.
- **Out of scope (unchanged from spec):** sidebar docking, layout/tab/field changes, JS behavior, `/comfybio/*` API. Popover and drag-lift shadows are left as-is (only the spec-named launcher and panel shadows are softened).
