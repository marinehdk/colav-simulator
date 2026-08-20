# C5 Implementation Notes — Product Shell Remainder (2026-08-19)

Work order: `docs/ui/C5-WORKORDER-20260819.md`. Prototype citations (P:...) refer to
`docs/ui/prototypes/openbridge-integration-shell/new-simulation-openbridge-integration-shell.html`.

## Files changed

| File | Delta |
|---|---|
| `web_gui/index.html` | `data-obc-theme="day"` on `<html>`; hidden `<obc-brilliance-menu id="brillianceMenu" variant="compact" aria-label="显示模式">` appended inside `.app-container` (P:2003); cache-bust tokens `?v=20260819-c4-situation-2` → `?v=20260819-c5-shell-1` for style.css, app.js, config-shell.js |
| `web_gui/style.css` | +~90 lines: theme layer (color-scheme dark for dusk/night; exact P:280-285 filters on `#validationScenarioImage` + `#simCanvas`; `.brilliance-menu-popover` per P:278); `--font-display/--font-ui/--font-body` Noto Sans/PingFang stack; body `font: 400 14px/1.7 var(--font-body); letter-spacing: 0`; `h1-h3` display stack (P:86-118); global `:focus-visible` (P:120) + html-wide `prefers-reduced-motion` (P:1558-1560) replacing the config-workface-scoped rules; new `@media (max-width: 520px)` tier (P:1530-1557 mapping); removed the two now-redundant scoped rules |
| `web_gui/app.js` | +~70 lines, one new section "OPENBRIDGE THEME" after the situationDisplay adapter: dynamic import of `brilliance-menu.js/+esm` from the pinned CDN base; `applyPalette(palette, persist=true)` (html dataset, `brillianceMenu.palette`, `topBar.dimmingButtonActivated` for dusk|night, localStorage `colav-openbridge-palette`, `situationDisplay.refreshPalette()`); `dimming-button-clicked` toggle; `palette-changed` → applyPalette; outside-click + Escape close with focus restore to the dimming button (P:3293 pattern); boot restore `applyPalette(initialPalette, false)`; no toast (ruling 2 deleted #9) |
| `web_gui/modules/config-shell.js` | `WORKFACE_TITLES` map; `switchWorkface` sets `document.title = '综合避碰仿真器 · <View>'`, persists localStorage `colav-workface`, invalid names coerce to `config`; new `restorePersistedWorkface()` called once in `bootConfig()` after `bindControls()`; no session-gating |
| `tests/web_gui/shell-theme.test.mjs` | new, 14 tests |
| `tests/web_gui/config-shell-static.test.mjs` | 1 assertion updated (see Deviations D8) |
| `docs/ui/CONFIG-FIDELITY-GAP-REPORT.md` | rows #5/#9: "Deleted by C5 ruling 2026-08-19 (deletion test)" |

Frozen modules zero-diff (verified `git status --porcelain` + a dedicated test):
`active-session-runtime.js`, `validation-assembly.js`, `telemetry-projection.js`,
`session-runtime-instance.js`, and `situation-display.js` (the palette seam is the
pre-existing exported `refreshPalette()`; no internal change was needed).

## Tests

- New `tests/web_gui/shell-theme.test.mjs`: 14 tests covering markup (theme attr,
  brilliance menu), app.js wiring (palette-changed / dimming-button-clicked /
  refreshPalette / both localStorage keys / outside-click+Esc / no-toast),
  style.css (color-scheme, exact per-theme filters, P:278 popover chrome, font
  stack, global focus + reduced-motion, 520 tier, surviving 1400/1050/820 tiers),
  config-shell (#22 title/persistence/boot restore), cache-bust token equality
  across the three changed assets, and frozen-module zero-diff via git.
- `config-shell-static.test.mjs`: updated the assertion that pinned the
  `.config-workface`-scoped `:focus-visible` rule (deleted by ruling 5) to pin the
  global rule instead.
- Suite: **135 pass / 0 fail** (`node --test tests/web_gui/*.test.mjs`,
  Node v22.18.0; baseline 121 + 14 new).

## Components and the palette

Verified against the pinned CDN asset: `openbridge.css` redefines the palette
custom properties on `:root[data-obc-theme="day"|"dusk"|"night"|"bright"]`
(e.g. `--element-active-color`, `--container-global-color`,
`--container-background-color`, `--border-divider-color`), and every obc-* web
component in use (top-bar, clock, icon-button, button, elevated-card,
number-input-field, scrollbar, card, brilliance-menu) consumes those variables in
its shadow styles — **no obc-* component ignores theming**; none needed patching.

Production surfaces that ignore palette switching (by design, recorded not
patched):

- Legacy Deployment chrome: `.glass-card` panels, playback buttons, planner
  cards, metric boxes etc. are styled from the frozen legacy token set
  (`--panel-bg`, `--glass-blur`, `--accent-cyan`...`--text-main`), which does not
  derive from OpenBridge variables. C5 scope is shell chrome only; the Deployment
  *canvas* is theme-adapted via the CSS filter on `#simCanvas`.
- `--situation-*` canvas palette tokens are static hex (C4/M5 ruling 10);
  `refreshPalette()` re-reads them on every palette change, so any future
  palette-driven token work needs no new seam.
- `.roadmap-workface` (Evaluation/Scenario/Algorithm placeholders) and
  `.openbridge-load-error` use fixed light hex — static content, outside scope.

## Deviations (justified)

- **D1 Popover top offset.** P:278 uses `top: calc(var(--topbar-h) + 8px)` with
  the bar flush to the viewport top. Production's `.app-container` pads 12px, so
  the bar's bottom edge sits at 68px; implemented `top: calc(12px + 56px +
  var(--s-2))` to preserve the binding visual contract ("8px below the bar")
  rather than the literal 64px, which would overlap the header by 4px. Right
  112px / width 304px / z-index 50 / position fixed are literal.
- **D2 No system-menu interplay.** Ruling 1 allowed mirroring P:3187-3193 only
  "if production's settings menu exists". Production `#settingsBtn` carries
  `aria-expanded` but has no popover or handler anywhere, so the dimming toggle
  does not touch it.
- **D3 Brilliance menu flags.** Markup carries `variant="compact"` per the
  ruling; `showBrightness=false` / `showPalette=true` are set as properties in
  app.js per P:2864-2869 (part of "FULL prototype behavior").
- **D4 Theme filter targets.** Filters apply to exactly `#validationScenarioImage`
  and `#simCanvas` as the ruling lists. `#validationRuleImage` is not filtered —
  the prototype likewise filters only `.enc-chart-image`/`.scenario-preview-image`,
  never the rule-guide media.
- **D5 520 stepper strip.** Prototype's 820-tier stepper re-shapes buttons to a
  2-column internal grid (P:1505); production keeps the existing
  `32px / 1fr / 10px` step grid (circle, title, dot) and only lays the four
  buttons into a `repeat(4, minmax(0,1fr))` row with `overflow-x: auto` +
  `scroll-snap-type: x proximity`. `.assembly-step small` state labels and
  `.config-progress` are hidden per P:1507. Zero JS changes, as ruled.
- **D6 520 top bar.** Work order says clock/alerts/sound hidden at 520 ("extend
  the 1400px pattern"); the prototype itself kept a slim clock at 520
  (P:1531-1532). The work order rules over the prototype here; the explicit 520
  rule is also redundant in practice because the 820 tier already hides all
  `.topbar-actions` — kept for contract explicitness.
- **D7 Session chip.** Ruling acknowledges the 820 tier already hides
  `.shell-session-state`; no 520 duplicate added.
- **D8 Updated one existing test.** `config-shell-static.test.mjs` asserted the
  scoped `.config-workface :focus-visible` selector that ruling 5 deletes;
  assertion re-pinned to the promoted global rule. No other baseline assertion
  touched.
- **D9 Dynamic import for the menu module.** app.js has no static CDN base (that
  lives in config-shell.js); the same pinned URL is used via dynamic `import()`
  with `.catch(() => {})`, matching the existing best-effort OpenBridge
  degradation philosophy (CDN failure leaves the menu inert; the shared error
  banner path is unaffected).

## Gates

- `node --test tests/web_gui/*.test.mjs` → 135 pass / 0 fail.
- `node --check web_gui/app.js`, `node --check web_gui/modules/config-shell.js` → OK.
- `git diff --check` → clean. Duplicate-id scan of index.html → none.
- No commits, nothing staged; `.codegraph/` untouched; `docs/ui/` not staged
  (gap-report edit + these notes only).
