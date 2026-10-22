import { VESSEL_ASSETS } from './vessel-assets.js?v=20261020-bulk';
export { VESSEL_ASSETS };

export function chooseVesselAsset(ship, explicitId) {
  if (String(ship.id) === '0') return {asset: VESSEL_ASSETS.fcb45, reason: '用户提供的本船外观，按遥测尺寸缩放'};
  if (explicitId && VESSEL_ASSETS[explicitId] && explicitId !== 'fcb45') return {asset: VESSEL_ASSETS[explicitId], reason: '手动外观示意，不改变船型数据'};
  // 20261020 用户裁决：OT/HO/CS 及多船场景所有目标船统一散货船 bulk_carrier——
  // 更大视觉目标利于 DT 视口 YOLO 检测；本船(id=0)与手动选择器逐船覆盖不受影响。
  return {asset: VESSEL_ASSETS.bulk_carrier, reason: '目标船统一散货船示意（20261020 裁决）'};
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
