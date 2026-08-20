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
npx esbuild entry.mjs --bundle --format=esm --minify \
  --outfile=<repo>/web_gui/vendor/openbridge/openbridge-components.mjs
cp node_modules/@oicl/openbridge-webcomponents/dist/openbridge.css \
  <repo>/web_gui/vendor/openbridge/openbridge.css
```

Then bump the `?v=` cache-bust on the bundle URL in `app.js` /
`modules/config-shell.js` and the `/static/vendor/openbridge/openbridge.css` href
in `index.html`. `tests/web_gui/shell-theme.test.mjs` asserts no CDN reference
remains in `app.js`.
