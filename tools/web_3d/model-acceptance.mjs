import assert from 'node:assert/strict';
import * as C from 'cesium';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {VESSEL_ASSETS,chooseVesselAsset,vesselModelMatrix} from '../../web_gui/modules/vessel-models.js';
const position=C.Cartesian3.fromDegrees(6.05,62.46,0.1);
const local=C.Matrix4.inverseTransformation(C.Transforms.eastNorthUpToFixedFrame(position),new C.Matrix4());
const report=[];
for(const asset of Object.values(VESSEL_ASSETS)) {
 const bytes=readFileSync(new URL('../../web_gui/'+asset.url.replace('/static/',''),import.meta.url));
 assert.equal(bytes.subarray(0,4).toString(),'glTF');
 assert.equal(createHash('sha256').update(bytes).digest('hex'),asset.sha256);
 const json=JSON.parse(bytes.subarray(20,20+bytes.readUInt32LE(12)).toString());
 for(const item of [...(json.buffers||[]),...(json.images||[])]) if(item.uri&&!item.uri.startsWith('data:')) {
  assert.ok(!/^(https?:|\/)/.test(item.uri));
  readFileSync(new URL(item.uri,new URL('../../web_gui/'+asset.url.replace('/static/',''),import.meta.url)));
 }
 for(const heading of [0,Math.PI/2,Math.PI,Math.PI*1.5]) {
  const m=vesselModelMatrix(C,position,heading,{length:45,width:8},asset);
  const forward=C.Matrix4.multiplyByPointAsVector(m,new C.Cartesian3(0,asset.forward==='+z'?-1:1,0),new C.Cartesian3());
  const vector=C.Matrix4.multiplyByPointAsVector(local,forward,new C.Cartesian3());
  C.Cartesian3.normalize(vector,vector);
  assert.ok(Math.abs(vector.x-Math.sin(heading))<1e-10);
  assert.ok(Math.abs(vector.y-Math.cos(heading))<1e-10);
  const beam=C.Matrix4.multiplyByPointAsVector(m,new C.Cartesian3(asset.beam,0,0),new C.Cartesian3());
  const length=C.Matrix4.multiplyByPointAsVector(m,new C.Cartesian3(0,asset.length,0),new C.Cartesian3());
  assert.ok(Math.abs(C.Cartesian3.magnitude(beam)-8)<1e-10);
  assert.ok(Math.abs(C.Cartesian3.magnitude(length)-45)<1e-10);
  const waterline=C.Matrix4.multiplyByPoint(m,new C.Cartesian3(asset.centerX,-asset.centerZ,asset.waterlineY),new C.Cartesian3());
  assert.ok(C.Cartesian3.distance(waterline,position)<1e-7);
 }
 report.push({asset:asset.id,hashVerified:true,localTextures:true,cardinalHeadings:4,scale45x8:true});
}
assert.equal(chooseVesselAsset({id:0},'tug').asset.id,'fcb45');
assert.equal(chooseVesselAsset({id:1,vessel_type:'tug'}).asset.id,'tug');
assert.equal(chooseVesselAsset({id:1},'ferry_roro').asset.id,'merchant_large_proxy');
console.log(JSON.stringify(report,null,2));
