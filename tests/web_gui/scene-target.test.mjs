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

test('P3-S5 obstacle cards carry the CONF row from the associated track existence',()=>{
 const tracked = {id:1,generation:2,x:1000,y:1000,psi:Math.PI,sog:5,ais:{age_s:0.4,state:'ACTIVE'}};
 const p = {raw:{run_id:'r',executed_tracker:'kf',os:{x:0,y:0,psi:0},obstacles:[tracked],
   tracks:[{labels:[7],generations:[2],states:[[1050,1000,0,0]],covariances:[],nis:[0],existence_prob:[0.997]}]},
   risk:{targets:[{targetId:1,generation:2,displayClass:'HIGH',encounter:'HEAD_ON',role:'GIVE_WAY',dcpaM:185.2,tcpaS:120}]}};
 const m = targetPresentation(p, tracked);
 const conf = m.metrics.find(item => item.label === 'CONF');
 assert.ok(conf, 'CONF row present on obstacle cards');
 assert.equal(conf.value, '0.997');
 // No track within the association radius renders an em dash.
 const empty = {raw:{...p.raw, tracks:[{labels:[],generations:[],states:[],covariances:[],nis:[],existence_prob:[]}]}, risk:p.risk};
 assert.equal(targetPresentation(empty, tracked).metrics.find(item => item.label === 'CONF').value, '—');
 // Legacy publishers without §6 fields still render the row as an em dash.
 const legacy = {raw:{...p.raw, tracks:[{labels:[7],generations:[2],states:[[1050,1000,0,0]],covariances:[],nis:[0]}]}, risk:p.risk};
 assert.equal(targetPresentation(legacy, tracked).metrics.find(item => item.label === 'CONF').value, '—');
 // The ownship (no ais object) omits the row entirely.
 const ownship = {id:0,x:0,y:0,psi:0,sog:5};
 assert.ok(!targetPresentation(p, ownship).metrics.some(item => item.label === 'CONF'));
});
