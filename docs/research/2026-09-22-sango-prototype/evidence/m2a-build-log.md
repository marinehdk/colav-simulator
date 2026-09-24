# M2-A build log — CC0 ship assets (Kenney Watercraft Kit)

Spec: issue #80 (Sango M2-A). Date: 2026-09-24. All commands run headless on
Unity 6000.3.24f1 at `/Applications/Unity/Hub/Editor/6000.3.24f1/Unity.app/Contents/MacOS/Unity`,
project `/Users/marine/Code/Colav-Simulator/sango`.

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
