import test from 'node:test';
import assert from 'node:assert/strict';
import { targetPresentation } from '../../web_gui/modules/scene-target.js';
import { buildSceneCompass } from '../../web_gui/modules/scene-compass.js';
const ship = {id:1,generation:2,x:1000,y:1000,psi:Math.PI,sog:5};
function fixture(encounter='HEAD_ON',role='GIVE_WAY',displayClass='HIGH') {
 return {raw:{run_id:'r',executed_tracker:'god',os:{x:0,y:0,psi:0},obstacles:[ship]},risk:{targets:[{targetId:1,generation:2,displayClass,encounter,role,dcpaM:185.2,tcpaS:120}]}};
}
test('AR target and compass share canonical alert colors; data uses current geometry and authoritative CPA',()=>{
 for(const state of ['CLEAR','LOW','HIGH']){
  const p=fixture('HEAD_ON','GIVE_WAY',state),m=targetPresentation(p,ship);
  assert.equal(m.alert.color,buildSceneCompass(p).targets[0].color);
  assert.equal(m.blocks[0].value,'45'); assert.equal(m.blocks[1].value,'0.76');
  assert.equal(m.blocks[2].value,'0.10'); assert.equal(m.metrics[3].value,'2.0');
 }
});
test('only canonical COLREG relationship chooses the official relation icon',()=>{
 for(const [encounter,role,icon] of [['HEAD_ON','GIVE_WAY','head-on'],['OVERTAKING','OVERTAKING','overtaking'],['CROSSING','GIVE_WAY','starboard-side'],['CROSSING','STAND_ON','port-side']]){
  const model=targetPresentation(fixture(encounter,role),ship);
  assert.equal(model.relation.icon,`obi-collision-avoidance-${icon}`);
 }
 assert.equal(targetPresentation(fixture('NONE','NONE'),ship).relation,null);
});
test('absent, stale or wrong-generation assessment keeps range but never invents CPA or encounter',()=>{
 for(const mutation of [p=>p.risk.targets=[],p=>p.risk.targets[0].generation=3,p=>p.risk.targets[0].observationHealth='STALE']){
  const p=fixture(); mutation(p); const m=targetPresentation(p,ship);
  assert.equal(m.alert.state,'unchecked');assert.equal(m.blocks[0].value,'45');assert.equal(m.blocks[1].value,'0.76');
  assert.equal(m.blocks[2].value,'—');assert.equal(m.metrics[3].value,'—');assert.equal(m.relation,null);
 }
});
test('outside the detection range stays white even if an old risk vector remains',()=>{
 const p=fixture('HEAD_ON','GIVE_WAY','HIGH');
 const far={...ship,x:2001,y:0};
 assert.deepEqual(targetPresentation(p,far).alert.state,'unchecked');
 assert.deepEqual(targetPresentation(p,far).alert.color,'#FFFFFF');
});
