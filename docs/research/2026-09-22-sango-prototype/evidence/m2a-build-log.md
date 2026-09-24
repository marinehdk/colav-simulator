# M2-A build log — CC0 ship assets (Kenney Watercraft Kit)

Spec: issue #80 (Sango M2-A). Date: 2026-09-24. All commands run headless on
Unity 6000.3.24f1 at `/Applications/Unity/Hub/Editor/6000.3.24f1/Unity.app/Contents/MacOS/Unity`,
project `/Users/marine/Code/Colav-Simulator/sango`.

> **2026-09-24 review fixes (post code-review of d1bc4f17..HEAD): Large class
> swapped ship-large → ship-cargo-a, catalog now persists measured end-taper
> widths (anti-flip bow guard), PROVENANCE.txt added. The tables in the
> original sections below reflect the FIRST build and are superseded by
> §Review fixes at the bottom.**

## Asset provenance

- Source: Kenney Watercraft Kit 2.1, License CC0 1.0.
- Zip pinned: `https://kenney.nl/media/pages/assets/watercraft-kit/a335cfed49-1713519620/kenney_watercraft-pack.zip` (~1.9 MB).
- Committed: `ship-large.fbx` (96 KB), `ship-ocean-liner.fbx` (92 KB),
  `boat-fishing-small.fbx` (32 KB), `Models/Textures/colormap.png` (12 KB),
  upstream `License.txt` verbatim as `Assets/Art/KenneyWatercraft/LICENSE.txt~`
  (Unity tilde convention: in repo, not imported as an asset).
- Excluded per spec: OBJ/GLB variants, all other kit models.

## Bow-direction pinning (evidence for the yaw literals)

Two independent sources, agreeing:

1. Kit preview renders (`Previews/*.png`, upscaled 64px → 512px for inspection):
   ship-large is a tall/sailing ship with pointed bow; ocean liner shows raked
   stem + counter stern; fishing boat shows wheelhouse forward of center,
   pointed hull forward, flat transom aft.
2. Kit OBJ vertex analysis (same geometry as FBX, plain text):
   - ship-large: hull width stays 4.4 units (full beam, flat transom) all the
     way to the Z-min tip; tapers 4.4 → 0.35 toward Z-max → **native bow +Z**.
   - ship-ocean-liner: keel outline (y=0) converges to a single point at
     z=-10.64 (stem reaches keel at tip); at z=+10.64 the keel is cut away
     (lowest vertex y=1.216 — counter stern) → **native bow −Z**.
   - boat-fishing-small: keel converges to a point at z=+1.935/1.585/1.081
     (per height level); flat transom at z=-1.935 → **native bow +Z**.
3. Cross-check inside Unity: the pipeline logs imported-mesh width-at-z-slice
   taper at build time (`[Sango.M2] bow evidence ...` in /tmp/m2a-pipeline.log):
   ship-large −Z 8.80 vs +Z 1.34 → bow +Z; liner −Z 5.72 vs +Z 6.75 → bow −Z;
   fishing −Z 3.57 vs +Z 2.76 → bow +Z. All match the pinned literals.

Pinned root yaw (bow → +Z): ship-large **0°**, ship-ocean-liner **180°**,
boat-fishing-small **0°**. Asserted as literals in `VesselCatalogTests`.

## Catalog values (pipeline output, `VesselCatalog.asset`)

| Class  | Prefab         | Model                | Target LOA | Actual LOA | Bow yaw | Waterline offset Y |
| ------ | -------------- | -------------------- | ---------- | ---------- | ------- | ------------------ |
| Large  | VesselLarge    | ship-large           | 100 m      | 100.0 m    | 0°      | −2.4045 m          |
| Medium | VesselMedium   | ship-ocean-liner     | 60 m       | 60.0 m     | 180°    | −1.2857 m          |
| Small  | VesselSmall    | boat-fishing-small   | 12 m       | 12.0 m     | 0°      | −0.3256 m          |

Waterline rule: draft = 15% × hull deck height. Hull deck height per model from
OBJ vertex-layer analysis (deck level / total model height):
ship-large 2.10/9.964 = 0.2108; liner 3.04/8.934 = 0.3403; fishing 0.70/2.6 = 0.2692.
Draft world = 0.15 × fraction × bounds.height × scale. Root pivot sits at hull
center; bottom of keel rests at root-local −draft.

## Test gates

- RED first: 18 tests, 0 passed / 18 failed (all "catalog asset missing" —
  correct seam failure, no compile errors). Results: /tmp/m2a-tests-red.xml.
- One real bug caught by the seam tests: materials authored with URP property
  name `_BaseMap` instead of HDRP's `_BaseColorMap` (silently dropped) →
  15/18 pass on first green attempt; fixed property name → green.
- GREEN: `Unity -batchmode -projectPath … -runTests -testPlatform EditMode
  -testResults /tmp/m2a-tests-green.xml -logFile /tmp/m2a-tests-green.log`,
  exit 0, **18 passed / 0 failed / 0 skipped**.

## Scene rebuild gate

`Unity -batchmode -quit -projectPath … -executeMethod
Sango.Editor.M1SceneBootstrapper.Build -logFile /tmp/m2a-scene.log` → exit 0,
`[Sango.M1] scene written: …/Assets/Scenes/M1-Weather.unity`. Git status after:
scene + FBX import settings (.meta) + generated prefabs/catalog/materials
dirty as expected. Ship placements baked into the scene:

- `Ships/VesselSmall`: position (14, −0.326, −6), yaw 20° (old Ship-0 spot).
- `Ships/VesselMedium`: position (−30, −1.286, 30), yaw −35°.
- `VesselLarge` NOT placed (reserved for M2-E per spec).

## Player build gate

`Unity -batchmode -quit -projectPath … -executeMethod
Sango.Editor.M1VerifyCapture.BuildStandalonePlayer -logFile /tmp/m2a-player.log`
(Mono backend) → **exit 0**, `Sango.M1] player build: Succeeded size=182MB
out=/Users/marine/Code/Colav-Simulator/sango/Builds/M1-Standalone.app`;
bundle exists on disk (183 MB).

## Commits

- `9de27091` feat(sango): M2-A import Kenney Watercraft Kit CC0 ship assets
- `d7e91aae` feat(sango): M2-A vessel pipeline + catalog, EditMode tests, M1 scene ships
- evidence: this file.

## Deviations / notes

- `ship-large` (the kit's only "large" model) renders as a tall/sailing ship,
  not a modern cargo vessel as the spec's prose describes. File choice kept
  per spec (class diversity target met); flagging for orchestrator acceptance.
- `M1-GlobalVolumeProfile.asset` regenerated (content-only diff, GUID stable)
  by the same scene-rebuild command and committed with it, so the tree stays
  clean; volume profile reference integrity verified via unchanged GUID.
- Visual acceptance (orchestrator, standalone player): look for two recognizable
  vessels at plausible scale — small fishing craft close-to-bridge right of
  center at (14,−6), 60 m liner mid-distance left at (−30,30); hulls should sit
  with ~15% of hull height in the water (no floating/sunk look), colormap
  textures (not magenta/white).

## Orchestrator visual acceptance (2026-09-24)

- Player screenshots (Standalone, windowed 1600x900, CUA capture; JPEG bytes):
  `m2a-b3-default.jpg` (B3 Moderate 4.5 m/s), `m2a-b0-calm.jpg` (B0 Calm 0.5 m/s,
  near-mirror sea), `m2a-b6-rough.jpg` (B6 Rough 12.5 m/s, wave texture visible).
- Keyboard hotkeys 0/6 driven through the accessibility path on the UNFOCUSED
  player; panel readouts match `BeaufortToWindSpeedMs` in all three states.
- Ships: liner + fishing boat textured from the kit colormap (no magenta/white),
  plausible draft (red anti-fouling band visible), plausible scale vs islands.
- Acceptance fix 1 — liner grounding: initial berth (-30,30) placed the liner
  22 m from seed-42 Island-5 center (visible shoreline ~0.8R ≈ 61 m) — aground.
  Deterministic re-derivation of the five island placements (PerlinIslandGenerator
  placement RNG is fully seed-determined) picked berth (30,90): ≥17 m clear of
  Island-5/Island-3 visible shorelines, bow/stern tip projections ≥15 m clear,
  azimuth separated from the fishing boat. Rebuilt scene + player, verified afloat.
- Acceptance fix 2 — unfocused rendering: the player never painted a frame when
  it could not take foreground focus (automation capture); `runInBackground` is
  now set at build time (ProjectSettings) and runtime (WeatherGUI.Awake), and
  captures are launched under `caffeinate` with per-app App Sleep disabled.
- Deferred to M2-E review: `ship-large` is a tall sailing ship (kit's only large
  model), not a cargo vessel as the spec prose suggested; not placed in this scene.

## Review fixes (2026-09-24, post code-review of d1bc4f17..HEAD)

### 1. Large class model swap: ship-large → ship-cargo-a

`ship-large` was the kit's only "large" model but is a tall SAILING ship;
spec #80 pins "large cargo vessel". Swapped to `ship-cargo-a.fbx` (container
feeder, aft bridge) at the same 100 m LOA target. `ship-large.fbx` and its
material removed from the repo; committed models are now exactly the three
class models (see `Assets/Art/KenneyWatercraft/PROVENANCE.txt`).

Bow re-pinning, dual evidence, both agreeing on **native bow +Z → yaw 0°**:

- Preview (`Previews/ship-cargo-a.png`, upscaled): containers fore, bridge
  and funnels on the aft (stern) end.
- OBJ vertex analysis: keel outline (y=0) runs flat to the −Z end (transom,
  z=−4.974, width 1.685) and converges to a point at +Z (±0.37 at z=+3.337,
  tip at z=+3.473); deck-plan width narrows toward the +Z tip (1.24/1.62 in
  the last two 5%-slices vs 3.70/2.76 at the −Z end) → **bow +Z**.
- Unity-side cross-check (pipeline measurement, 10 z-slices, outer-20%
  average): −Z end 7.61 vs +Z end 5.31 → +Z finer → bow +Z. Consistent.

Deck-height fraction re-derived: main deck edge at y=0.966 (full-length
z-span level), total height 3.380 → fraction 0.966/3.380 = 0.2858.
Draft = 0.15 × 0.2858 × height × scale → waterline offset −1.37 m at 100 m LOA.

### 2. Anti-flip bow guard (catalog-persisted taper)

The rotation test alone was a literal echo (a flipped pin passed all tests).
`VesselCatalog.Entry` now carries `bowEndWidth` / `sternEndWidth` — the
pipeline-measured near-end hull widths of the native ±Z ends, mapped
bow/stern by the pinned yaw at build time. New test
`Catalog_TaperTowardPinnedBow_IsStrictlyFiner_ThanStern` asserts
`bowEndWidth < sternEndWidth` (geometry-derived, not an echo). Red-check
performed: flipping the Large yaw literal to 180°, rebuilding the catalog and
re-running tests → the taper test goes RED ("bow end 7.61 should be finer
than stern end 5.31") while the literal-echo rotation test alone cannot see
the geometry contradiction. Reverted to 0°, catalog rebuilt, all green.

### 3. Provenance file

`Assets/Art/KenneyWatercraft/PROVENANCE.txt` (TextAsset): kit name+version,
upstream zip URL, source page, CC0 1.0 statement, verbatim-license pointer
(`LICENSE.txt~`), and the three committed models. `LICENSE.txt~` kept as the
verbatim license.

### 4. Catalog version stamp

`VesselCatalog.pipelineVersion` (currently 2) — `EnsureBuilt()` rebuilds
unless the catalog's version matches, so spec changes force regeneration on
the next scene build instead of being skipped by the "3 valid entries" check.

### Post-fix catalog values (pipeline output, pipelineVersion 2)

| Class  | Prefab       | Model              | LOA target → actual | Bow yaw (evidence)              | bowEndW / sternEndW | Waterline offset |
| ------ | ------------ | ------------------ | ------------------- | ------------------------------- | ------------------- | ---------------- |
| Large  | VesselLarge  | ship-cargo-a       | 100 → 100.0 m       | 0° (keel point + deck taper +Z) | 5.31 / 7.61         | −1.37 m          |
| Medium | VesselMedium | ship-ocean-liner   | 60 → 60.0 m         | 180° (keel point −Z)            | 5.72 / 6.75         | −1.29 m          |
| Small  | VesselSmall  | boat-fishing-small | 12 → 12.0 m         | 0° (keel point +Z)              | 2.76 / 3.57         | −0.33 m          |

(End widths in import-scale units from the pipeline's 10-slice measurement;
they are ratios-as-evidence, not physical meters.)

### Post-fix gates

- EditMode: `… -runTests -testPlatform EditMode -testResults
  /tmp/m2a-tests-green3.xml` → exit 0, **21 passed / 0 failed / 0 skipped**
  (18 original + 3 taper). Red-check run for the flip experiment:
  /tmp/m2a-tests-flip.xml (19 pass / 2 fail, both expected).
- Scene rebuild: `… -executeMethod Sango.Editor.M1SceneBootstrapper.Build`
  → exit 0 (EnsureBuilt skips via matching pipelineVersion after the forced
  regeneration during the swap; the scene re-berth (30,90) from f7a4b321
  untouched).
- Player build: `… -executeMethod Sango.Editor.M1VerifyCapture.BuildStandalonePlayer`
  → exit 0 (see /tmp/m2a-player2.log).

