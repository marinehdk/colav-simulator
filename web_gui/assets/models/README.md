# Vessel display assets

Integrated at the user's request on 2026-09-20. These meshes affect presentation only. They do not define COLREG class, dimensions, draft, collision geometry, dynamics, or authority.

- `fcb45/ownship.glb`: user-supplied `FCB45_Cesium_LOD0_v0.glb`; SHA-256 in `catalog.json`. Engineering visualization v0, not shipyard CAD. Source principal hull length 45m, beam 8m; extra fenders/appendages extend beyond that hull. glTF +Y up, bow -Z, origin at midship design waterline. Runtime length/beam remain authoritative; smaller non-FCB test scenarios display a scaled visual proxy.
- `targets/kenney/`: ten models from Kenney Watercraft Kit, [official CC0 source](https://kenney.nl/assets/watercraft-kit). Downloaded from the URLs supplied in the user's archive, with external `Textures/colormap.png` retained. Bow +Z (narrow bow end checked against stern cross sections); up +Y. Grounded origin; the catalog declares an estimated display waterline.
- `targets/3dassets/`: [cabin fishing boat](https://3dassets.dev/assets/harbor-and-tackle-cabin-fishing-boat-686960fe), [RIB](https://3dassets.dev/assets/transport-collection-hd-rigid-inflatable-a8316db9), and [Ro-Ro stern section](https://3dassets.dev/assets/ferry-terminal-and-harbour-crossing-ferry-terminal-and-c0fcd3aa). Publisher lists CC0. RIB is explicitly +Z bow and keel-based. **The Ro-Ro is only a stern section**: retained as downloaded source material but excluded from the runtime whole-vessel catalog. No tanker/bulk-carrier identities are invented from a generic merchant mesh.

The supplied ZIP contained a manifest and downloader, not the model binaries. Its script was inspected, not executed. Thirteen GLBs and the shared texture were fetched from the listed public sources and validated as files; twelve complete target models are selectable. `targets/asset-manifest.json` records URLs, file sizes and checksums. `bounds.json` records scene-node-transformed bounds, including quantized accessors. `catalog.json` freezes scale, bow and waterline mappings; `vessel-assets.js` is its generated browser representation.

`tools/web_3d/inspect_models.py` and `build_model_catalog.py` reproduce metadata. `model-acceptance.mjs` verifies local texture resolution, checksums, 000/090/180/270-degree transformations, and 45m × 8m runtime scaling. Cesium is explicitly configured with `upAxis=Y, forwardAxis=X`: the loader applies Y-up conversion only; the catalog performs bow alignment without Cesium's additional default Z-to-X rotation.

Unknown target type uses an explicitly marked visual proxy. The target card's appearance selector is a local, run/generation-scoped visual override; it sends no API mutation and never changes telemetry. Source categories are used only when explicit vessel-type metadata exists. Production uses this library and an explicit point marker on load failure; the superseded generated block hull was removed.

CC0 legal text: <https://creativecommons.org/publicdomain/zero/1.0/>. The user-supplied FCB asset retains its user-provided provenance; this document does not relicense it as third-party CC0.

## FCB45 visual revision v1 (2026-09-21)

The original supplied GLB is preserved as `fcb45/ownship.glb`. Its 171 primitives
have POSITION but no NORMAL attributes. Cesium's material pipeline therefore
selects unlit shading, explaining the flat pastel panels. The runtime now uses
`fcb45/ownship-v1.glb`, with unit normals on every primitive, explicit linear
PBR colors, and 11 material batches rather than 171 separate primitives.

The user's five FCB45 reference images guide the v1 hull taper/chines and sheer,
raked wraparound bridge glazing, window frames, black boot-top and diagonal
livery, rubber rubbing strakes, raised tire sidewalls, deck seams, rails,
bollards, access stairs and aft equipment. Mast and propulsion details retained
from v0 are identified in `refinement-v1.json`. Old thruster discs that no longer
lay on the revised hull skin are not retained as floating geometry.

Principal hull length45m/beam8m, glTF +Y up/-Z bow, and waterline origin remain
unchanged. Runtime telemetry still owns actual vessel dimensions and motion.
This is reference-driven visual reconstruction, not a surveyed CAD, lines plan,
collision mesh or hydrodynamic calibration. Image inconsistencies and unseen
surfaces cannot establish engineering dimensions.

Rebuild (isolated build-only dependency; simulator environment unchanged):

```sh
uv pip install --python .venv/bin/python --target /tmp/fcb45-visual-tools --no-deps trimesh==4.7.4
PYTHONPATH=/tmp/fcb45-visual-tools .venv/bin/python tools/web_3d/refine_fcb45.py
.venv/bin/python tools/web_3d/inspect_models.py
.venv/bin/python tools/web_3d/build_model_catalog.py
node --test tests/web_gui/fcb45-asset.test.mjs
```

The inspection page `tests/web_gui/fcb45-visual.html` compares original,
normals-only and v1 geometry with identical cameras and lighting. The runtime
uses an explicitly illustrative daylight key and low-order ambient illumination
so ship contours remain legible independently of wall-clock sun position;
night/dusk lower the display illumination. Neither is a simulated light sensor.
