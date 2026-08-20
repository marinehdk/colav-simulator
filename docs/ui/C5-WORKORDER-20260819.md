# C5 — Product Shell Remainder Work Order (2026-08-19)

Worktree: `$HOME/Code/.worktrees/Colav-Simulator/mass-openbridge-ui` (branch `codex/mass-openbridge-ui`).
NEVER touch `.codegraph/`; do NOT stage `docs/ui/`; no commits/push. Bump `?v=` cache-bust token in index.html for every changed browser-served asset.

Prototype (binding visual contract): `docs/ui/prototypes/openbridge-integration-shell/new-simulation-openbridge-integration-shell.html` (cited as P:line below).

## Approved rulings (user-confirmed 2026-08-19 — binding)

1. **#4 Theme switching — FULL prototype behavior.**
   - `index.html`: add `data-obc-theme="day"` to `<html>`; add hidden `<obc-brilliance-menu id="brillianceMenu" variant="compact" aria-label="显示模式">` popover (P:2003, P:278 styling: fixed, top calc(topbar+8px), right 112px, width 304px, z-index 50).
   - app.js: import the brilliance-menu component module from the CDN base already used for icons (P:11). Palette state day/dusk/night/bright; `applyPalette(palette, persist=true)` sets `document.documentElement.dataset.obcTheme`, `topBar.dimmingButtonActivated = palette is dusk|night` (P:2853-2862), persists `localStorage 'colav-openbridge-palette'`, and calls `situationDisplay.refreshPalette()`. Restore saved palette at boot (no persist).
   - Toggle: `mainTopBar.addEventListener('dimming-button-clicked', ...)` flips menu.hidden; closes system menu if open (production `settingsBtn` uses aria-expanded popover — mirror P:3187-3193 but adapted to production's settings menu if it exists; if production settings button has no popover, just don't touch it).
   - `palette-changed` event → applyPalette (P:3196-3198). NO toast notification (ruling: #9 deleted) — feedback is the visible theme change itself.
   - Outside-click + Esc close menu (P:3293 pattern); stopPropagation inside menu.
   - style.css: `html[data-obc-theme="dusk"], html[data-obc-theme="night"] { color-scheme: dark; }` + image filters EXACTLY per P:280-285 mapped to production elements: ENC/reference preview image (`#validationScenarioImage`) and Deployment canvas (`#simCanvas`) get the same filter classes (add stable classes or attribute selectors). Note: CDN openbridge.css already flips the OpenBridge variables per `[data-obc-theme]`, and production `--ob-*` derives from them — do NOT hand-write palette hex sheets.
   - Verify obc-* components (clock, buttons, steps) actually restyle under theme change (they read the same variables); record any that don't in impl notes rather than patching component internals.
2. **#5 integration app bar — DELETED** (no content exists for it; pure chrome). **#9 toasts — DELETED** (event log + inline notices + badges cover all real notification needs; no second adapter). Append a short disposition note to `docs/ui/CONFIG-FIDELITY-GAP-REPORT.md` rows #5/#9: "Deleted by C5 ruling 2026-08-19 (deletion test)".
3. **#8 Responsive 520 tier + horizontal stepper.** Implement P:1499-1557 contract: ≤520px — config workface becomes single column; Assembly Steps become a horizontal scrollable stepper strip (step buttons in a row, scroll-snap ok); top bar degrades (clock/alerts/sound hidden — extend existing 1400px pattern); session chip hidden (820px pattern already hides); Deployment sidebars stack. Layout CSS only — zero JS logic changes. Keep existing 1050/820 tiers.
4. **#6 Typography minimal.** style.css: `--font-display: "Noto Sans","PingFang SC",sans-serif; --font-ui/--font-body → same stack (keep existing var names, add --font-display)`; body `font: 400 14px/1.7 var(--font-body); letter-spacing: 0;` h1-h3 use --font-display (P:86-118). No webfont import (system-installed Noto/PingFang fallback chain).
5. **#7 Global focus/motion.** Promote the scoped `.config-workface :focus-visible` rule (style.css:310) to global `:focus-visible { outline: 3px solid var(--ob-accent-mid); outline-offset: 2px; }` (P:120); promote `prefers-reduced-motion` block (style.css:311) from config-workface scope to html-wide. Remove the now-redundant scoped rules (keep `.choice:focus-visible::part(wrapper)` — shadow-part specific).
6. **#22 doc-title + view persistence.** In `config-shell.js` `switchWorkface(name)`: `document.title = '综合避碰仿真器 · ' + display name (Config/Deployment/Evaluation/Scenario/Algorithm)`; persist `localStorage 'colav-workface'`; at boot, restore saved workface if valid (default config). No session-gating: restoring Deployment without a session shows its existing empty state (already handled).

## Constraints

- Shell must NOT own Validation/Runtime/telemetry/ENC/evaluation truth — theme/persistence/title only touch chrome. `switchWorkface` stays the single authority for panel toggling.
- Frozen modules zero-diff: `active-session-runtime.js`, `validation-assembly.js`, `telemetry-projection.js`, `session-runtime-instance.js`. `situation-display.js` may receive ONLY the existing `refreshPalette()` call from app.js (no internal changes expected; if a change is truly needed, justify in notes).
- Lit gotchas: attribute names all-lowercase; shadow-origin events don't reach light-DOM listeners — bind directly; `customElements.whenDefined` resolves before first render.
- Tests (node --test, deterministic): extend `config-shell-static.test.mjs` and/or new `shell-theme.test.mjs`: assert html has data-obc-theme + brilliance-menu markup; app.js contains palette-changed/dimming-button-clicked wiring + refreshPalette call + localStorage keys; style.css contains theme filter rules + global :focus-visible + global reduced-motion + 520 tier media + font stack; config-shell switchWorkface sets document.title + persists; index.html cache-bust bumped.
- Gates: Node suite (121 baseline) green + new; `node --check` changed JS; `git diff --check`; dup-id check; no pixel automation.

## Sequence (TDD)

M1 tests red → M2 #6/#7 (pure CSS, smallest) → M3 #22 (JS+tests) → M4 #4 theme (markup+JS+CSS) → M5 #8 520 tier (CSS) → M6 gap-report disposition notes + impl notes. Report: files changed, test count, any component that ignores theme, deviations.
