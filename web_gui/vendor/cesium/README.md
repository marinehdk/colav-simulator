# Local 3D runtime

CesiumJS **1.133.0**, Apache-2.0; retain `LICENSE.md`, `ThirdParty.json`, `ThirdParty.extra.json` and visible Cesium credits. Assets, workers and widgets are served locally. The application disables default imagery, geocoding and ion services; no ion token is needed. Only the browser bundle is shipped; duplicate Node/ESM bundles are omitted.

Projection: **proj4 2.19.10**, MIT, sibling `proj4/` bundle and license.

Rebuild both runtimes and the extended OpenBridge 1.0.1 bundle:

```sh
npm ci --prefix tools/web_3d --ignore-scripts
node tools/web_3d/build-vendor.mjs
python3 tools/web_3d/inspect_models.py
python3 tools/web_3d/build_model_catalog.py
```

The lockfile freezes transitive dependencies. The build retains the pre-existing table-header alignment CSS patch and deliberately avoids esbuild syntax minification for the OpenBridge Lit templates. Vessel sources, waterline conventions and source checksums are recorded in `web_gui/assets/models/README.md`; model inspection uses the project Python environment.
