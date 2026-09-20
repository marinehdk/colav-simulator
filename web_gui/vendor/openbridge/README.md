# OpenBridge vendored bundle

Runtime files:

- `openbridge-components.mjs` — esbuild bundle (minified ESM, lit inlined) of every
  OpenBridge web component + icon the shell uses. Loaded by
  `modules/config-shell.js` (`loadOpenBridge`) and `app.js` (brilliance-menu path).
- `openbridge.css` — verbatim stylesheet from the same package. Referenced by
  `index.html` (`#openbridgeStyles`).
- `entry-source.mjs` — the exact static-import entry the bundle was built from.

No CDN requests at runtime. Version pin: `@oicl/openbridge-webcomponents@1.0.1`.

## Rebuild (e.g. version bump or adding a component)

```sh
mkdir -p /tmp/ob-vendor && cd /tmp/ob-vendor && npm init -y
npm i @oicl/openbridge-webcomponents@1.0.1 esbuild
# edit entry-source.mjs here first (note: compass/depth-actual/pitch-roll live
# under dist/navigation-instruments/, not dist/components/)
npx esbuild entry.mjs --bundle --format=esm \
  --minify-whitespace --minify-identifiers \
  --outfile=<repo>/web_gui/vendor/openbridge/openbridge-components.mjs
cp node_modules/@oicl/openbridge-webcomponents/dist/openbridge.css \
  <repo>/web_gui/vendor/openbridge/openbridge.css
```

Do not enable esbuild syntax minification for `1.0.1`: it rewrites the Lit
`classMap()` template used by dropdown/event items and causes a runtime directive
error. Whitespace + identifier minification keeps the bundle compact without
changing tagged-template structure.

Then bump the `?v=` cache-bust on the bundle URL in `app.js` /
`modules/config-shell.js` and the `/static/vendor/openbridge/openbridge.css` href
in `index.html`. `tests/web_gui/shell-theme.test.mjs` asserts no CDN reference
remains in `app.js`.

## AR integration (2026-09-20)

The selective entry now includes POI Layer and POI Vessel, with their upstream dependencies. Version stays 1.0.1. Rebuild with `tools/web_3d/build-vendor.mjs` and its pinned npm lockfile. That build also preserves the existing table-header alignment token customization. POI Controller is not used: its image/video detection mapping does not implement 3D projection. App code supplies CSS-pixel `x`, pointer line length `y`, and `buttonY`; `y` alone is not an absolute screen ordinate.

The build also gives the upstream POI Group wrapper button an accessible
Chinese label (`展开重叠目标组`). Grouping/layout remains upstream behavior;
the scene handles Escape through the component's public `expand` property.
