# Config Visual Fidelity Restoration Pass — Work Order (2026-08-19)

All rulings below are USER-APPROVED (2026-08-19). Do not re-open them.

## Scope (13 items IN, this pass)

From `docs/ui/CONFIG-FIDELITY-GAP-REPORT.md`:

- **#10** Rule choice cards → `obc-elevated-card` 4-column grid; aria-pressed selected (accent-pale fill + 2px accent-mid outline); disabled `.56` opacity + click suppression + Enter/Space activation.
- **#11** Scenario + ENC selection → `obc-scrollbar` horizontal snap carousels (2 cards per view) with prev/next `obc-icon-button`, auto-disable at scroll bounds. Preserve disabled-option tooltip-reason semantics.
- **#12** Scenario preview → static SVG overlay: route centerline/boundary/corridor, vessel markers (42px circular badges, per-marker heading rotation, gold target border, mono labels), map scale. **Draw ONLY from geometry already exposed client-side (catalog/scenario facts). Missing geometry → omit that layer. NEVER invent values.** (#12 is also a C4 grilling topic later; this pass is the static first cut.)
- **#12a** Rogaland scenarios: styled placeholder frame (no invented geography).
- **#13** Algorithm selection → carousel; tracker → 2-column choice grid.
- **#14** Algorithm detail chrome → role eyebrow + grade pill + 20px h2 + summary + 3-stage flow + facts dl + binding footer (icon badge, "Exact tuple compatible", tuple id mono). Keep existing classification-card semantics.
- **#15** Params → `obc-number-input-field` with inline `error`/`errorText`. **Keep the notices live-region for tuple-level/runtime-level messages** (approved: inline errors + notices coexist). Field-level validation errors move inline.
- **#16** Execution-plan → 4-metric strip (accent 25px numerals), Session Clock timeline track + start/end markers + facts, Deterministic Seeds (seed root + stream cards + facts), READY/INVALID footer. Data: existing only.
- **#17 is OUT (intentional deviation)** — Guardrails & Evidence section stays declined. Do NOT add.
- **#18** Inspector → `assembly-status` pill (DRAFT/READY/CREATED color-coded) + 44px-header sections + sticky Default/Create `obc-button`.
- **#19** Stepper chrome → 28px circular mono numbers, completion dots, 3px inset accent bar on selected, "N of 4 ready" + 4px progress track filled 25% per ready step.
- **#20** Create semantics → when draft clean (matches active / no dirty changes), swap Create button to "Open Deployment" jump action instead of disabled Create. Dirty → Create as today.
- **#21** Rule-guide → floating prev/next `obc-icon-button`s over media (multiship Rule 16/17 switching).
- **#3 (Config part)** Token layer: port the OpenBridge palette custom-properties block (prototype P:64-99 as reference token sheet: `--container-section-color`, `--element-active-color`, `--border-divider-color`, accent `--instrument-enhanced-secondary-color`, danger `--alert-alarm-color`, `color-mix` derivatives, spacing 4-32, radius 6, shadow, 44px targets, 3px accent focus-visible, reduced-motion) into `style.css`; map **Config-scope** selectors onto tokens replacing hardcoded hex. Do NOT restyle Deployment/global shell (C5 will generalize).

## OUT of scope (do not touch)

- Gaps #1-9, #22 (top bar populate, tab icons/pill, theme switching, app bar, typography global, focus-visible GLOBAL, responsive 520 tier, toasts, doc-title/persistence) → C5-shell.
- `modules/validation-assembly.js` — ZERO changes (DOM-free core).
- `modules/active-session-runtime.js` — frozen.
- `app.js` — untouched except if a page-assert in test_web_api.py requires sync (prefer not touching app.js at all).
- Deployment workface markup/styles, ENC canvas.

## Hard constraints

- Prototype file `docs/ui/prototypes/openbridge-integration-shell/new-simulation-openbridge-integration-shell.html` is the BINDING VISUAL CONTRACT — read it for the exact look (line refs in gap report). NEVER copy its JS wholesale into production; behavior stays in config-shell.js render functions.
- Keep ALL production-only additions: REFERENCE PREVIEW badge, openbridge-load-error banner, retry-catalog button, shell-session-state chip, contract-boundary note, evidence-detail note, scenario-facts dl.
- OpenBridge stays pinned CDN `@oicl/openbridge-webcomponents@1.0.1`; load any additionally needed components (obc-elevated-card, obc-icon-button, obc-number-input-field, obc-scrollbar, obc-button) from the same pin. Failure mode: page must remain usable if a component fails (progressive: existing native semantics may remain as fallback content where cheap).
- Protected paths never staged: `.codegraph/`, `docs/ui/`. Work order file itself lives in docs/ui/ — do not commit it.
- Chinese UI copy conventions as in current file.

## TDD protocol (per milestone)

1. Extend `tests/web_gui/config-shell-static.test.mjs` (and `tests/test_web_api.py` page asserts where markup they pin changes) FIRST — RED.
2. Implement markup/CSS/JS in `web_gui/index.html`, `web_gui/style.css`, `web_gui/modules/config-shell.js`.
3. GREEN.

## Gates (all must pass; exact commands from worktree root)

```bash
/Users/marine/.nvm/versions/node/v22.18.0/bin/node --test tests/web_gui/*.test.mjs   # all green (baseline 82; count will grow)
/Users/marine/.nvm/versions/node/v22.18.0/bin/node --check web_gui/modules/config-shell.js
$HOME/Code/Colav-Simulator/.venv/bin/pytest -q tests/test_validation_config_api.py tests/test_p1_capability_api.py tests/test_p1_clock_enc_contract.py tests/test_playback_speed.py tests/test_web_api.py   # 40 passing baseline
git diff --check
perl -ne 'print "DUP:$1\n" if /id="([^"]+)"(?{ $seen{$1}++ == 1 and print STDERR \"dup $1\\n\" })/' web_gui/index.html   # no duplicate ids
```

Do NOT commit — main agent reviews, runs browser smoke, and commits selectively.

## Milestone order (commit-sized)

M1 token layer (#3-part) → M2 stepper+inspector (#19, #18, #20) → M3 rules (#10, #21) → M4 scenarios (#11, #12, #12a) → M5 algorithms (#13, #14) → M6 params (#15, #16).

After each milestone run the node gate; after M6 run all gates.
