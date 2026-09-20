import test from 'node:test';
import assert from 'node:assert/strict';
import { createGeography, geographyProblem, riskForTarget, poiState, targetKey } from '../../web_gui/modules/scene-geography.js';
import { readFileSync } from 'node:fs';
const fixture = JSON.parse(readFileSync(new URL('./fixtures/scene-geography.json', import.meta.url)));

test('UTM positions match backend CRS transforms across both supported zones and full ENC grid', () => {
  for (const item of fixture) {
    const geo = createGeography(item.info);
    for (const point of item.points) {
      const [lon, lat] = geo.lonLat(point.north, point.east);
      const distance = Math.hypot((lon - point.lon) * Math.cos(lat * Math.PI / 180), lat - point.lat) * 111320;
      assert.ok(distance < 0.5, `${item.info.utm_zone}: ${distance}m`);
    }
    for (const angle of [0, Math.PI / 2, Math.PI, -Math.PI / 2, Math.PI - 1e-7, -Math.PI + 1e-7]) {
      const actual = geo.heading(3000, 3000, angle);
      const a = geo.lonLat(3000, 3000), b = geo.lonLat(3000 + 100 * Math.cos(angle), 3000 + 100 * Math.sin(angle));
      const expected = Math.atan2((b[0] - a[0]) * Math.cos(a[1] * Math.PI / 180), b[1] - a[1]);
      assert.ok(Math.abs(Math.atan2(Math.sin(actual - expected), Math.cos(actual - expected))) < 0.0001);
    }
  }
});

test('unknown CRS, missing origin and cross-session geography fail closed', () => {
  const info = fixture[0].info;
  for (const bad of [{...info, horizontal_crs:null},{...info,origin_e:null},{...info,hemisphere:'south'}]) assert.ok(geographyProblem(bad, info.run_id));
  assert.ok(geographyProblem(info, 'another-run'));
});

test('AR uses canonical class, generation and unavailable semantics rather than CPA thresholds', () => {
  const target = {id:2,generation:3};
  const risk = {targetId:2,generation:2,displayClass:'HIGH',dcpaM:0};
  assert.equal(riskForTarget({risk:{targets:[risk]}}, target), null);
  risk.generation = 3;
  assert.equal(riskForTarget({risk:{targets:[risk]}}, target), risk);
  assert.equal(poiState(risk), 'alarm');
  assert.equal(poiState({...risk,displayClass:'CLEAR',dcpaM:0}), 'checked');
  assert.equal(poiState({...risk,unavailableReasons:['STALE']}), 'unchecked');
  assert.equal(poiState(null), 'unchecked');
  assert.notEqual(targetKey('run1',target),targetKey('run2',target));
});

test('prediction timestamps come from plan evidence, never invented from display frame rate', async () => {
  const { predictionMarkers } = await import('../../web_gui/modules/scene-geography.js');
  const data = { plans: { prediction_horizon: [[0,0],[1,1],[2,2],[3,3]] } };
  assert.deepEqual(predictionMarkers(data), []);
  data.planner = {horizon_dt_s:60};
  assert.deepEqual(predictionMarkers(data).map(x=>x.elapsed), [60,120,180]);
  data.plans.prediction_render = {style:'REJECTED',ownship:{time_s:[0,60,120,180]}};
  assert.deepEqual(predictionMarkers(data), []);
  data.plans.prediction_render.style='ACTIVE';
  data.plans.prediction_render.ownship.time_s=[30,60,120,180];
  assert.deepEqual(predictionMarkers(data).map(x=>x.elapsed), [90,150]);
});

test('offscreen hints use the projected nearest edge, including above and below', async () => {
 const {offscreenDirection} = await import('../../web_gui/modules/scene-geography.js');
 for(const [point,edge] of [[{x:500,y:-10},'up'],[{x:500,y:900},'down'],[{x:-30,y:400},'left'],[{x:1200,y:400},'right']])
  assert.equal(offscreenDirection(point,1000,800,true,true).edge,edge);
 assert.match(offscreenDirection(null,1000,800,false,true).arrow,/后方/);
});

test('visual asset choices never infer AIS facts or change authoritative dimensions', async () => {
 const {chooseVesselAsset,VESSEL_ASSETS}=await import('../../web_gui/modules/vessel-models.js');
 const ship=Object.freeze({id:1,length:12,width:3});
 assert.equal(chooseVesselAsset(ship,'tug').asset.id,'tug');
 assert.match(chooseVesselAsset(ship,'tug').reason,/手动/);
 assert.equal(chooseVesselAsset(ship).asset.id,'rib');
 assert.equal(ship.length,12);
 assert.equal(VESSEL_ASSETS.ferry_roro,undefined);
 assert.equal(chooseVesselAsset({id:0,length:45,width:8}).asset.id,'fcb45');
});
