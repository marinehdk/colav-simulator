/**
 * Radar PPI panel (P3-S1, spec #90) — plan-position-indicator canvas for the
 * sensor-model-v1 radar_x X-band model.
 *
 * Data contract:
 * - Target blips come from the full-1.0 transport measurements
 *   (envelope.measurements[0][0], the ownship first sensor group), the same
 *   cache the situation-display measurements layer consumes.
 * - Clutter speckle is regenerated browser-side as a deterministic seeded
 *   Poisson process from the additive envelope field `radar_ppi`
 *   (RadarXBand.ppi_descriptor, gui_server `_radar_ppi_descriptor`): same
 *   parameterization (rate, range decay, sea state, blind ring, cap) and the
 *   same seed -> the same speckle every frame and every reload.
 * - Blip intensity follows the shared SNR model (range equation, mirror of
 *   sensing.RadarXBand.snr_db) so bright = high SNR = high PD.
 *
 * Pure functions are exported for tests; createRadarPpi owns only canvas
 * drawing and visibility state (no clock, no network).
 */

export const N_METERS_PER_NM = 1852;

/** Mirrors sensing.RadarXParams power-detection defaults (milliampere-ch5 §5.1). */
export const SNR_MODEL_DEFAULT = Object.freeze({
  snrRefDb: 13.0,
  refRangeM: 5556.0,
  refRcsM2: 10.0,
  decayDbPerDecade: 40.0,
});

/** Milliampere-ch5 §5.1 range scale table (nm). */
export const RANGE_SCALES_NM_DEFAULT = Object.freeze([0.75, 1.5, 3, 6, 12, 24]);

/** Envelope descriptor stand-in when the session has no radar_x sensor yet. */
export const PPI_DESCRIPTOR_DEFAULT = Object.freeze({
  schema_version: 'radar-ppi@1',
  seed: 0,
  spokes: 2048,
  scan_period_s: 2.5,
  range_scales_nm: RANGE_SCALES_NM_DEFAULT,
  range_scale_nm: 6,
  blind_ring_m: 54.0,
  clutter_rate_per_m2: 5e-7,
  clutter_range_decay: 2.0,
  clutter_ref_range_m: 1000.0,
  sea_state_beaufort: 3,
  clutter_db_per_beaufort: 3.0,
  max_measurements_per_scan: 400,
});

const TWO_PI = Math.PI * 2;

/** Deterministic 32-bit PRNG (mulberry32). */
export function mulberry32(seed) {
  let state = seed >>> 0;
  return function next() {
    state = (state + 0x6D2B79F5) | 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Shared SNR model: SNR(r, rcs) = ref + 10 log10(rcs/rcsRef) - decay log10(r/ref). */
export function snrProxyDb(rangeM, rcsM2 = SNR_MODEL_DEFAULT.refRcsM2, model = SNR_MODEL_DEFAULT) {
  const floor = Math.max(rangeM, 1);
  return (
    model.snrRefDb
    + 10 * Math.log10(rcsM2 / model.refRcsM2)
    - model.decayDbPerDecade * Math.log10(floor / model.refRangeM)
  );
}

/** Normalized blip intensity [0.08, 1] from the shared SNR curve. */
export function ppiIntensity(rangeM, rcsM2 = SNR_MODEL_DEFAULT.refRcsM2, model = SNR_MODEL_DEFAULT) {
  const snr = snrProxyDb(rangeM, rcsM2, model);
  return Math.min(1, Math.max(0.08, (snr - 0) / 18));
}

/** Sweep azimuth (rad, compass from north) for a simulation time; wraps per scan. */
export function sweepAzimuthRad(simTimeS, scanPeriodS) {
  if (!(scanPeriodS > 0)) return 0;
  return (((simTimeS / scanPeriodS) % 1) + 1) % 1 * TWO_PI;
}

/** Analytic Poisson mean over the annulus (mirror of RadarXBand.expected_clutter_count). */
export function expectedClutterCount({ rangeScaleM, blindRingM, ratePerM2, rangeDecay, refRangeM, seaFactor = 1 }) {
  const rMin = Math.max(blindRingM, 1);
  const rMax = Math.max(rangeScaleM, rMin * 1.01);
  const integral = Math.abs(rangeDecay - 2) < 1e-9
    ? Math.log(rMax / rMin)
    : (rMax ** (2 - rangeDecay) - rMin ** (2 - rangeDecay)) / (2 - rangeDecay);
  return TWO_PI * ratePerM2 * seaFactor * refRangeM ** rangeDecay * integral;
}

/**
 * Deterministic clutter speckle for one scan: Poisson cardinality + inverse-CDF
 * radius sampling on (r_ref/r)^decay, uniform azimuth. Same seed + scanIndex
 * reproduces the same points (backend-independent realization of the same
 * parameterized process).
 */
export function clutterPoints({ seed, scanIndex, rangeScaleM, descriptor = PPI_DESCRIPTOR_DEFAULT, count = null }) {
  const blindRingM = Number.isFinite(descriptor.blind_ring_m) ? descriptor.blind_ring_m : 54.0;
  const ratePerM2 = descriptor.clutter_rate_per_m2 ?? PPI_DESCRIPTOR_DEFAULT.clutter_rate_per_m2;
  const rangeDecay = descriptor.clutter_range_decay ?? 2.0;
  const refRangeM = descriptor.clutter_ref_range_m ?? 1000.0;
  const dbPerBeaufort = descriptor.clutter_db_per_beaufort ?? 3.0;
  const beaufort = descriptor.sea_state_beaufort ?? 3;
  const cap = descriptor.max_measurements_per_scan ?? 400;
  const seaFactor = 10 ** (0.1 * dbPerBeaufort * (beaufort - 3));
  const lambda = expectedClutterCount({ rangeScaleM, blindRingM, ratePerM2, rangeDecay, refRangeM, seaFactor });
  const prng = mulberry32((seed >>> 0) ^ ((scanIndex % 4294967296) >>> 0));
  // Knuth Poisson draw (lambda stays small at the contract rate).
  let poisson = 0;
  let threshold = Math.exp(-lambda);
  let product = prng();
  while (product > threshold && poisson < 100000) {
    poisson += 1;
    product *= prng();
  }
  const n = Math.min(count ?? poisson, cap);
  const rMin = Math.max(blindRingM, 1);
  const rMax = Math.max(rangeScaleM, rMin * 1.01);
  // Inverse-CDF over a fixed radius grid (same statistics as per-cell thinning).
  const grid = [];
  for (let i = 0; i <= 256; i += 1) grid.push(rMin + ((rMax - rMin) * i) / 256);
  const weights = grid.map(r => r ** (1 - rangeDecay));
  const total = weights.reduce((sum, w) => sum + w, 0);
  const points = [];
  for (let i = 0; i < n; i += 1) {
    let target = prng() * total;
    let radius = grid[grid.length - 1];
    for (let g = 0; g < grid.length; g += 1) {
      target -= weights[g];
      if (target <= 0) { radius = grid[g]; break; }
    }
    const azimuth = prng() * TWO_PI;
    points.push({ rangeM: radius, azimuthRad: azimuth, intensity: 0.12 + 0.5 * prng() });
  }
  return points;
}

/** Projects a relative NE position to canvas pixels (north up, ownship centered). */
export function ppiProject(northRelM, eastRelM, rangeScaleM, sizePx) {
  const fraction = rangeScaleM > 0 ? Math.hypot(northRelM, eastRelM) / rangeScaleM : 0;
  return {
    x: sizePx / 2 + (eastRelM / (rangeScaleM || 1)) * (sizePx / 2),
    y: sizePx / 2 - (northRelM / (rangeScaleM || 1)) * (sizePx / 2),
    inside: fraction <= 1,
    rangeFraction: fraction,
  };
}

/** Range-ring distances (m) for the active scale: thirds plus the outer ring. */
export function rangeRingsM(rangeScaleM) {
  if (!(rangeScaleM > 0)) return [];
  return [rangeScaleM / 3, (2 * rangeScaleM) / 3, rangeScaleM];
}

/**
 * Builds the render model from one telemetry envelope.
 *
 * Target blips: envelope.measurements[0][0] entries with do_idx >= 0 (radar
 * measurements in absolute world NE), positioned relative to envelope.os.
 * Clutter: deterministic regeneration via clutterPoints keyed on
 * (seed, scanIndex = floor(sim_time / scan_period)).
 */
export function buildPpiModel(envelope, { rangeScaleNm = null, descriptor = null } = {}) {
  const resolvedDescriptor = descriptor ?? envelope?.radar_ppi ?? PPI_DESCRIPTOR_DEFAULT;
  const scales = Array.isArray(resolvedDescriptor.range_scales_nm) && resolvedDescriptor.range_scales_nm.length
    ? resolvedDescriptor.range_scales_nm
    : RANGE_SCALES_NM_DEFAULT;
  const resolvedScaleNm = rangeScaleNm ?? resolvedDescriptor.range_scale_nm ?? scales[Math.min(3, scales.length - 1)];
  const rangeScaleM = resolvedScaleNm * N_METERS_PER_NM;
  const blindRingM = resolvedDescriptor.blind_ring_m ?? 0;
  const scanPeriodS = resolvedDescriptor.scan_period_s ?? 2.5;
  const simTimeS = Number.isFinite(Number(envelope?.sim_time)) ? Number(envelope.sim_time) : 0;
  const os = envelope?.os;

  const model = {
    descriptor: resolvedDescriptor,
    rangeScaleNm: resolvedScaleNm,
    rangeScaleM,
    blindRingM,
    scanPeriodS,
    simTimeS,
    sweepAzRad: sweepAzimuthRad(simTimeS, scanPeriodS),
    scanIndex: scanPeriodS > 0 ? Math.floor(simTimeS / scanPeriodS) : 0,
    ownshipHeadingRad: Number.isFinite(os?.psi) ? Number(os.psi) : (Number(os?.cog) || 0),
    hasOwnship: Number.isFinite(os?.north) && Number.isFinite(os?.east),
    blips: [],
    clutter: [],
  };
  if (!model.hasOwnship) return model;

  const sensorGroups = envelope?.measurements?.[0];
  const radarGroup = Array.isArray(sensorGroups) ? sensorGroups.find(group => Array.isArray(group)) : null;
  for (const measurement of radarGroup || []) {
    if (!Array.isArray(measurement) || !Array.isArray(measurement[1])) continue;
    const [doIdx, ne] = measurement;
    if (doIdx === undefined || doIdx === null || doIdx < 0) continue; // clutter regenerated below
    if (!Number.isFinite(ne[0]) || !Number.isFinite(ne[1])) continue;
    const northRel = ne[0] - Number(os.north);
    const eastRel = ne[1] - Number(os.east);
    const rangeM = Math.hypot(northRel, eastRel);
    if (rangeM > rangeScaleM || rangeM < blindRingM) continue;
    model.blips.push({
      id: doIdx,
      rangeM,
      azimuthRad: ((Math.atan2(eastRel, northRel) % TWO_PI) + TWO_PI) % TWO_PI,
      intensity: ppiIntensity(rangeM),
      northRel,
      eastRel,
    });
  }
  model.clutter = clutterPoints({
    seed: Number.isFinite(Number(resolvedDescriptor.seed)) ? Number(resolvedDescriptor.seed) : 0,
    scanIndex: model.scanIndex,
    rangeScaleM,
    descriptor: resolvedDescriptor,
  });
  return model;
}

/** Renders one PPI frame; owns no clock and no network. */
export function createRadarPpi({ canvas, onState = () => {} } = {}) {
  if (!canvas) throw new Error('radar-ppi requires canvas');
  const ctx = canvas.getContext('2d');
  let descriptor = PPI_DESCRIPTOR_DEFAULT;
  let rangeScaleNm = PPI_DESCRIPTOR_DEFAULT.range_scale_nm;
  let visible = false;
  let lastModel = buildPpiModel(null, {});

  function palette() {
    if (typeof document === 'undefined' || typeof getComputedStyle !== 'function') {
      return { surface: '#04140F', grid: '#1E4D3A', text: '#9FB8AD', accent: '#39D98A' };
    }
    const computed = getComputedStyle(document.documentElement);
    return {
      surface: computed.getPropertyValue('--ppi-surface').trim() || '#04140F',
      grid: computed.getPropertyValue('--ppi-grid').trim() || '#1E4D3A',
      text: computed.getPropertyValue('--ppi-text').trim() || '#9FB8AD',
      accent: computed.getPropertyValue('--ppi-accent').trim() || '#39D98A',
    };
  }

  function prepareCanvas() {
    const width = canvas.clientWidth || 320;
    const height = canvas.clientHeight || 320;
    const dpr = typeof window === 'undefined' ? 1 : (window.devicePixelRatio || 1);
    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { width, height };
  }

  function ringLabel(distanceM) {
    return distanceM >= 1000 ? `${(distanceM / N_METERS_PER_NM).toFixed(2).replace(/\.?0+$/, '')} nm` : `${Math.round(distanceM)} m`;
  }

  function draw() {
    const { width, height } = prepareCanvas();
    const colors = palette();
    const size = Math.min(width, height);
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = size / 2 - 14;
    const scalePx = radius * 2;
    ctx.clearRect(0, 0, width, height);

    ctx.save();
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, TWO_PI);
    ctx.fillStyle = colors.surface;
    ctx.fill();
    ctx.clip();

    // Afterglow sweep wedge behind the rotating beam.
    const sweepCanvas = model => model.sweepAzRad - Math.PI / 2;
    const sweep = sweepCanvas(lastModel);
    const wedge = ctx.createLinearGradient(centerX, centerY, centerX + Math.cos(sweep) * radius, centerY + Math.sin(sweep) * radius);
    wedge.addColorStop(0, 'rgba(57, 217, 138, 0.35)');
    wedge.addColorStop(1, 'rgba(57, 217, 138, 0.0)');
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.arc(centerX, centerY, radius, sweep - Math.PI / 5, sweep);
    ctx.closePath();
    ctx.fillStyle = wedge;
    ctx.fill();

    // Range rings + cross hairs + bearing ticks.
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1;
    for (const ring of rangeRingsM(lastModel.rangeScaleM).slice(0, 2)) {
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius * (ring / lastModel.rangeScaleM), 0, TWO_PI);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.moveTo(centerX - radius, centerY); ctx.lineTo(centerX + radius, centerY);
    ctx.moveTo(centerX, centerY - radius); ctx.lineTo(centerX, centerY + radius);
    ctx.stroke();
    for (let deg = 0; deg < 360; deg += 30) {
      const rad = (deg * Math.PI) / 180;
      const inner = radius - (deg % 90 === 0 ? 8 : 4);
      ctx.beginPath();
      ctx.moveTo(centerX + Math.sin(rad) * inner, centerY - Math.cos(rad) * inner);
      ctx.lineTo(centerX + Math.sin(rad) * radius, centerY - Math.cos(rad) * radius);
      ctx.stroke();
    }

    // Deterministic regenerated clutter speckle.
    ctx.fillStyle = 'rgba(159, 184, 173, 0.55)';
    for (const point of lastModel.clutter) {
      const px = centerX + Math.sin(point.azimuthRad) * radius * (point.rangeM / lastModel.rangeScaleM);
      const py = centerY - Math.cos(point.azimuthRad) * radius * (point.rangeM / lastModel.rangeScaleM);
      ctx.fillRect(px, py, 1.6, 1.6);
    }

    // Target blips (latest radar measurements), brightness = shared SNR proxy.
    for (const blip of lastModel.blips) {
      const projected = ppiProject(blip.northRel, blip.eastRel, lastModel.rangeScaleM, scalePx);
      ctx.beginPath();
      ctx.arc(centerX + projected.x - scalePx / 2, centerY + projected.y - scalePx / 2, 2 + 2.5 * blip.intensity, 0, TWO_PI);
      ctx.fillStyle = `rgba(57, 217, 138, ${0.35 + 0.6 * blip.intensity})`;
      ctx.fill();
    }

    // Sweep line + ownship marker + bow line.
    ctx.strokeStyle = colors.accent;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(centerX + Math.cos(sweep) * radius, centerY + Math.sin(sweep) * radius);
    ctx.stroke();

    ctx.save();
    ctx.translate(centerX, centerY);
    ctx.rotate(lastModel.ownshipHeadingRad);
    ctx.fillStyle = '#EAF6FF';
    ctx.strokeStyle = '#123C70';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(0, -10);
    ctx.lineTo(4, -3);
    ctx.lineTo(3, 9);
    ctx.lineTo(-3, 9);
    ctx.lineTo(-4, -3);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
    ctx.restore();

    // Static bezel + labels.
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, TWO_PI);
    ctx.stroke();
    ctx.fillStyle = colors.text;
    ctx.font = '10px JetBrains Mono, monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText('N', centerX - 4, centerY - radius + 10);
    ctx.fillText(ringLabel(lastModel.rangeScaleM), centerX + 6, centerY - radius + 24);
    const rings = rangeRingsM(lastModel.rangeScaleM);
    if (rings.length >= 2) ctx.fillText(ringLabel(rings[1]), centerX + 6, centerY - radius / 3 + 6);
    canvas.setAttribute(
      'aria-label',
      `X 波段雷达 PPI，量程 ${lastModel.rangeScaleNm} 海里，目标 ${lastModel.blips.length}，杂波 ${lastModel.clutter.length}`,
    );
  }

  const resizeObserver = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => {
    if (visible) draw();
  });
  resizeObserver?.observe(canvas);

  return {
    render(model) {
      lastModel = model || buildPpiModel(null, { descriptor, rangeScaleNm });
      if (visible) draw();
      onState({ visible, rangeScaleNm: lastModel.rangeScaleNm, blips: lastModel.blips.length, clutter: lastModel.clutter.length });
    },
    setDescriptor(next) {
      descriptor = next && typeof next === 'object' ? next : PPI_DESCRIPTOR_DEFAULT;
      if (!descriptor.range_scales_nm?.includes(rangeScaleNm)) rangeScaleNm = descriptor.range_scale_nm ?? RANGE_SCALES_NM_DEFAULT[3];
    },
    setRangeScale(nm) {
      const value = Number(nm);
      if (Number.isFinite(value) && value > 0) {
        rangeScaleNm = value;
        draw();
        onState({ visible, rangeScaleNm, blips: lastModel.blips.length, clutter: lastModel.clutter.length });
      }
    },
    options() { return { rangeScaleNm, descriptor }; },
    visible() { return visible; },
    setVisible(next) {
      visible = Boolean(next);
      if (visible) draw();
      onState({ visible, rangeScaleNm, blips: lastModel.blips.length, clutter: lastModel.clutter.length });
    },
    toggle() { this.setVisible(!visible); },
    destroy() { resizeObserver?.disconnect(); },
  };
}
