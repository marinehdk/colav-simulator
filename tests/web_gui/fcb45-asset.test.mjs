import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const root=new URL('../../web_gui/assets/models/fcb45/',import.meta.url);
function glb(name){const bytes=readFileSync(new URL(name,root));const size=bytes.readUInt32LE(12);return{json:JSON.parse(bytes.subarray(20,20+size).toString()),bin:bytes.subarray(28+size)};}
test('FCB lighting regression: v0 had no normals; all v1 rendered primitives have finite unit normals',()=>{
 const before=glb('ownship.glb');assert.ok(before.json.meshes.every(m=>m.primitives.every(p=>p.attributes.NORMAL===undefined)));
 const {json,bin}=glb('ownship-v1.glb');
 for(const mesh of json.meshes)for(const p of mesh.primitives){
  assert.notEqual(p.attributes.NORMAL,undefined);
  const a=json.accessors[p.attributes.NORMAL],b=json.bufferViews[a.bufferView];assert.equal(a.componentType,5126);assert.equal(a.count,json.accessors[p.attributes.POSITION].count);
  const offset=(b.byteOffset||0)+(a.byteOffset||0),stride=b.byteStride||12;
  for(let i=0;i<a.count;i++){const n=[0,1,2].map(j=>bin.readFloatLE(offset+i*stride+j*4));assert.ok(n.every(Number.isFinite));assert.ok(Math.abs(Math.hypot(...n)-1)<1e-4);}
 }
 assert.ok(json.meshes.length<=12,'material batching limits draw calls');
});
test('reference-driven visible details and source provenance are reproducible',()=>{
 const report=JSON.parse(readFileSync(new URL('refinement-v1.json',root)));const names=report.parts.map(p=>p.name).join('\n');
 for(const feature of ['Closed transom','Diagonal hull livery','Outward raked wraparound glazing','Bridge window mullion','Work deck cross seam','Mooring bollard','Port access stair','Side tire fender','Transom tire fender'])assert.ok(names.includes(feature),feature);
 assert.ok(report.triangles<50000);assert.equal(report.source_sha256,'843e94e92e663c9174506db88ac1ec771647a40edd8ee7397e70ae9c4df9d035');
});
