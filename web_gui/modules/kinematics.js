/**
 * Shared pure kinematic interpolation math (ticket #71, decision D5).
 *
 * ONE module owns scalar linear interpolation and shortest-angle heading
 * interpolation. The live presentation buffer (telemetry-playback.js), the
 * Situation Display (situation-display.js) and the Replay source adapter
 * (replay-source.js) all consume this math; their spread/fallback semantics
 * differ by mode and stay in those modules. No state, no DOM, no network.
 */

export const LINEAR_VESSEL_KEYS = ['x', 'y', 'north', 'east', 'latitude', 'longitude', 'sog', 'u', 'v'];
export const ANGULAR_VESSEL_KEYS = ['psi', 'cog'];

export function lerpScalar(from, to, amount) {
  return from + (to - from) * amount;
}

export function interpolateAngle(from, to, amount) {
  if (!Number.isFinite(from) || !Number.isFinite(to)) return to;
  const delta = Math.atan2(Math.sin(to - from), Math.cos(to - from));
  return from + delta * amount;
}

/**
 * Interpolated values for every key finite in BOTH frames: linear keys via
 * lerpScalar, angular keys via shortest-path interpolateAngle. Keys missing
 * or non-finite in either frame are never invented.
 */
export function interpolateVesselKinematics(from, to, amount, keys = [...LINEAR_VESSEL_KEYS, ...ANGULAR_VESSEL_KEYS]) {
  const values = {};
  for (const key of keys) {
    const fromValue = from[key];
    const toValue = to[key];
    if (!Number.isFinite(fromValue) || !Number.isFinite(toValue)) continue;
    values[key] = ANGULAR_VESSEL_KEYS.includes(key)
      ? interpolateAngle(fromValue, toValue, amount)
      : lerpScalar(fromValue, toValue, amount);
  }
  return values;
}
