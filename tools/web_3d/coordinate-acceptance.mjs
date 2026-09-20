import assert from 'node:assert/strict';
import * as C from 'cesium';
import {createGeography} from '../../web_gui/modules/scene-geography.js';
import {createEncGeometry} from '../../web_gui/modules/scene-3d.js';
const report=[];
for(const zone of [32,33]) {
 const info={ready:true,run_id:'control',utm_zone:zone,horizontal_crs:`EPSG:${25800+zone}`,hemisphere:'north',display_height_reference:'ellipsoid-zero-visual-only',origin_e:39000,origin_n:6956450,width:6000,height:6000};
 const geo=createGeography(info),mesh=createEncGeometry(C,geo),positions=mesh.attributes.position.values;
 let maximum=0;
 const vertex=i=>C.Cartesian3.fromArray(positions,i*3);
 for(let row=0;row<32;row++)for(let col=0;col<32;col++)for(const [u,v] of [[.23,.37],[.67,.74],[.5,.5]]) {
  const base=row*33+col;
  const vertices=u+v<=1?[base,base+1,base+33]:[base+34,base+33,base+1];
  const weights=u+v<=1?[1-u-v,u,v]:[u+v-1,1-u,1-v];
  const interpolated=new C.Cartesian3();
  vertices.forEach((index,i)=>C.Cartesian3.add(interpolated,C.Cartesian3.multiplyByScalar(vertex(index),weights[i],new C.Cartesian3()),interpolated));
  const exact=C.Cartesian3.fromDegrees(...geo.lonLat((row+v)*6000/32,(col+u)*6000/32),.1);
  maximum=Math.max(maximum,C.Cartesian3.distance(exact,interpolated));
 }
 assert.ok(maximum<=1,`zone${zone} mesh error ${maximum}m`);
 assert.equal(mesh.attributes.st.values[0],0);assert.equal(mesh.attributes.st.values[1],0);
 assert.equal(mesh.attributes.st.values.at(-1),1);
 report.push({zone,interiorSamples:3072,maxEcefInterpolationErrorM:maximum});
}
console.log(JSON.stringify(report,null,2));
