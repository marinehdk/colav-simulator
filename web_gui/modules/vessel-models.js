import { VESSEL_ASSETS } from './vessel-assets.js?v=20260921-fcb-v1';
export { VESSEL_ASSETS };

export function chooseVesselAsset(ship, explicitId) {
  if (String(ship.id) === '0') return {asset: VESSEL_ASSETS.fcb45, reason: '用户提供的本船外观，按遥测尺寸缩放'};
  if (explicitId && VESSEL_ASSETS[explicitId] && explicitId !== 'fcb45') return {asset: VESSEL_ASSETS[explicitId], reason: '手动外观示意，不改变船型数据'};
  const type = String(ship.vessel_type ?? ship.ship_type ?? '').toLowerCase();
  const byClass = {cargo:'cargo_large',passenger:'passenger',tug:'tug',workboat:'tow_workboat',fishing:'fishing_cabin_realistic',sailing:'sailing',pleasure:'pleasure_hsc',small_craft:'rib'};
  if (byClass[type]) return {asset:VESSEL_ASSETS[byClass[type]],reason:'按船型元数据选择的示意外观'};
  return {asset:VESSEL_ASSETS[ship.length < 25 ? 'rib' : 'merchant_large_proxy'],reason:'船型未知：通用外观代理'};
}

export function vesselModelMatrix(C, position, trueHeading, ship, asset) {
  const length = Number.isFinite(ship.length) && ship.length > 0 ? ship.length : asset.length;
  const beam = Number.isFinite(ship.width) && ship.width > 0 ? ship.width : asset.beam;
  // Loader explicitly uses upAxis=Y, forwardAxis=X: only Y-up conversion,
  // not Cesium's additional default Z-forward -> X-forward rotation.
  // The registry owns bow orientation: [x,y,z] -> [x,-z,y].
  const matrix = C.Transforms.headingPitchRollToFixedFrame(position,
    new C.HeadingPitchRoll(trueHeading + (asset.forward === '+z' ? Math.PI : 0), 0, 0));
  C.Matrix4.multiplyByScale(matrix,new C.Cartesian3(beam/asset.beam,length/asset.length,length/asset.length),matrix);
  return C.Matrix4.multiplyByTranslation(matrix,new C.Cartesian3(-asset.centerX,asset.centerZ,-asset.waterlineY),matrix);
}
