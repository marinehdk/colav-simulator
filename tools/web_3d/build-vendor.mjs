// npm ci --prefix tools/web_3d --ignore-scripts && node tools/web_3d/build-vendor.mjs
import { build } from 'esbuild';
import { cp, readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../../', import.meta.url));
const deps = fileURLToPath(new URL('./node_modules/', import.meta.url));
const vendor = path.join(root, 'web_gui/vendor');
// Preserve the existing project's table-header alignment customization.
const table = path.join(deps, '@oicl/openbridge-webcomponents/dist/components/table-header-item/table-header-item.css.js');
await writeFile(table, (await readFile(table, 'utf8')).replace('text-align: left;', 'text-align: var(--menu-navigation-components-table-header-item-label-align, left);'));
const group = path.join(deps, '@oicl/openbridge-webcomponents/dist/ar/poi-group/poi-group.js');
await writeFile(group, (await readFile(group, 'utf8')).replace('@click=${this.onClick}\n            class=', 'aria-label="展开重叠目标组"\n            @click=${this.onClick}\n            class='));
// 1.0.1's vessel wrapper omits the official button's relation slot/property.
// Forward them without changing the upstream button, icons, or grouping logic.
const vessel = path.join(deps, '@oicl/openbridge-webcomponents/dist/ar/poi-vessel/poi-vessel.js');
let vesselSource = await readFile(vessel, 'utf8');
if (!vesselSource.includes('slot="relation"')) {
  vesselSource = vesselSource
    .replace('this.vesselInteractive = false;', 'this.vesselInteractive = false;\n    this.hasRelation = false;')
    .replace('.data=${this.data}', '.data=${this.data}\n        .hasRelation=${this.hasRelation}')
    .replace('</obc-poi-button-vessel>', '<slot name="relation" slot="relation"></slot>\n      </obc-poi-button-vessel>')
    .replace('ObcPoiVessel = __decorateClass([', '__decorateClass([property({ type: Boolean })], ObcPoiVessel.prototype, "hasRelation", 2);\nObcPoiVessel = __decorateClass([');
  await writeFile(vessel, vesselSource);
}
await build({ entryPoints: [path.join(vendor, 'openbridge/entry-source.mjs')], nodePaths: [deps], bundle: true, format: 'esm', minifyWhitespace: true, minifyIdentifiers: true, outfile: path.join(vendor, 'openbridge/openbridge-components.mjs') });
await mkdir(path.join(vendor, 'proj4'), {recursive: true});
await build({entryPoints:[path.join(deps,'proj4/lib/index.js')],bundle:true,format:'esm',minify:true,outfile:path.join(vendor,'proj4/proj4.mjs')});
await cp(path.join(deps,'proj4/LICENSE.md'),path.join(vendor,'proj4/LICENSE.md'));
await cp(path.join(deps,'cesium/Build/Cesium'),path.join(vendor,'cesium'), {recursive:true,filter:src=>!src.endsWith('.map')});
for (const file of ['index.js','index.cjs']) await rm(path.join(vendor,'cesium',file),{force:true});
for (const file of ['LICENSE.md','ThirdParty.json','ThirdParty.extra.json']) await cp(path.join(deps,'cesium',file),path.join(vendor,'cesium',file));
