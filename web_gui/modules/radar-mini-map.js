import { TARGET_RISK_STYLES } from './situation-display.js?v=20260826-radar-card-v1';

export const RADAR_FORWARD_HALF_ANGLE_RAD = Math.PI / 3;

const RADAR_RISK_COLORS = Object.freeze({
  safe: TARGET_RISK_STYLES.safe.outlineColor,
  warn: TARGET_RISK_STYLES.warn.outlineColor,
  danger: TARGET_RISK_STYLES.danger.outlineColor,
  unknown: '#4F5B60',
});

export function buildRadarModel(snapshot, rangeM, targetRiskLevels = {}) {
  const os = snapshot?.os;
  const resolvedRangeM = Number(rangeM);
  const model = {
    rangeM: Number.isFinite(resolvedRangeM) && resolvedRangeM > 0 ? resolvedRangeM : 0,
    ownshipHeadingRad: Number.isFinite(os?.psi) ? Number(os.psi) : (Number(os?.cog) || 0),
    forwardHalfAngleRad: RADAR_FORWARD_HALF_ANGLE_RAD,
    targets: [],
  };
  if (!model.rangeM || !Number.isFinite(os?.x) || !Number.isFinite(os?.y)) return model;

  model.targets = (snapshot?.obstacles || []).flatMap((target) => {
    if (!Number.isFinite(target?.x) || !Number.isFinite(target?.y)) return [];
    const relativeNorth = Number(target.x) - Number(os.x);
    const relativeEast = Number(target.y) - Number(os.y);
    if (Math.hypot(relativeNorth, relativeEast) > model.rangeM) return [];
    const projectedRisk = String(targetRiskLevels[String(target.id)] || 'unknown');
    return [{
      id: target.id,
      northFraction: relativeNorth / model.rangeM,
      eastFraction: relativeEast / model.rangeM,
      headingRad: Number.isFinite(target.cog)
        ? Number(target.cog)
        : (Number.isFinite(target.psi) ? Number(target.psi) : 0),
      riskLevel: RADAR_RISK_COLORS[projectedRisk] ? projectedRisk : 'unknown',
    }];
  });
  return model;
}

export function createRadarMiniMap({ canvas }) {
  if (!canvas) throw new Error('radar-mini-map requires canvas');
  const ctx = canvas.getContext('2d');
  let lastModel = buildRadarModel(null, 0);

  function palette() {
    if (typeof document === 'undefined' || typeof getComputedStyle !== 'function') {
      return { background: '#F7F8FA', border: '#AAB4BA', text: '#5C666B' };
    }
    const computed = getComputedStyle(document.documentElement);
    return {
      background: computed.getPropertyValue('--ob-surface').trim() || '#F7F8FA',
      border: computed.getPropertyValue('--ob-border').trim() || '#AAB4BA',
      text: computed.getPropertyValue('--ob-subtle').trim() || '#5C666B',
    };
  }

  function prepareCanvas() {
    const width = canvas.clientWidth || 240;
    const height = canvas.clientHeight || 240;
    const dpr = typeof window === 'undefined' ? 1 : (window.devicePixelRatio || 1);
    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { width, height };
  }

  function drawBracket(x, y, color) {
    const half = 10;
    const corner = 5;
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.6;
    ctx.setLineDash([3, 2]);
    ctx.beginPath();
    ctx.moveTo(x - half, y - half + corner); ctx.lineTo(x - half, y - half); ctx.lineTo(x - half + corner, y - half);
    ctx.moveTo(x + half - corner, y - half); ctx.lineTo(x + half, y - half); ctx.lineTo(x + half, y - half + corner);
    ctx.moveTo(x + half, y + half - corner); ctx.lineTo(x + half, y + half); ctx.lineTo(x + half - corner, y + half);
    ctx.moveTo(x - half + corner, y + half); ctx.lineTo(x - half, y + half); ctx.lineTo(x - half, y + half - corner);
    ctx.stroke();
    ctx.restore();
  }

  function drawHeadingTriangle(x, y, headingRad, color) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(headingRad);
    ctx.strokeStyle = color;
    ctx.fillStyle = 'rgba(255,255,255,0.78)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(0, -8);
    ctx.lineTo(-5, 6);
    ctx.lineTo(5, 6);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  function drawOwnship(x, y, headingRad) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(headingRad);
    ctx.setLineDash([]);
    ctx.fillStyle = '#FFFFFF';
    ctx.strokeStyle = '#123C70';
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(0, -13);
    ctx.lineTo(5, -5);
    ctx.lineTo(4, 12);
    ctx.lineTo(-4, 12);
    ctx.lineTo(-5, -5);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  function draw(model) {
    const { width, height } = prepareCanvas();
    const colors = palette();
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.max(24, Math.min(width, height) / 2 - 12);
    ctx.clearRect(0, 0, width, height);

    ctx.save();
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.fillStyle = colors.background;
    ctx.fill();
    ctx.clip();

    const headingCanvas = model.ownshipHeadingRad - Math.PI / 2;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.arc(
      centerX,
      centerY,
      radius,
      headingCanvas - model.forwardHalfAngleRad,
      headingCanvas + model.forwardHalfAngleRad,
    );
    ctx.closePath();
    ctx.fillStyle = 'rgba(71, 146, 226, 0.20)';
    ctx.fill();

    ctx.strokeStyle = colors.border;
    ctx.lineWidth = 1;
    ctx.setLineDash([]);
    for (const fraction of [0.5, 1]) {
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius * fraction, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.moveTo(centerX - radius, centerY); ctx.lineTo(centerX + radius, centerY);
    ctx.moveTo(centerX, centerY - radius); ctx.lineTo(centerX, centerY + radius);
    ctx.stroke();

    ctx.strokeStyle = '#1F5C97';
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(
      centerX + Math.sin(model.ownshipHeadingRad) * radius,
      centerY - Math.cos(model.ownshipHeadingRad) * radius,
    );
    ctx.stroke();

    model.targets.forEach((target) => {
      const x = centerX + target.eastFraction * radius;
      const y = centerY - target.northFraction * radius;
      const color = RADAR_RISK_COLORS[target.riskLevel] || RADAR_RISK_COLORS.unknown;
      drawBracket(x, y, color);
      drawHeadingTriangle(x, y, target.headingRad, color);
    });
    drawOwnship(centerX, centerY, model.ownshipHeadingRad);
    ctx.restore();

    ctx.strokeStyle = colors.border;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = colors.text;
    ctx.font = '9px "Noto Sans", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('N', centerX, centerY - radius + 9);
    ctx.fillText('E', centerX + radius - 9, centerY);
    ctx.fillText('S', centerX, centerY + radius - 9);
    ctx.fillText('W', centerX - radius + 9, centerY);
    const ringLabel = (distanceM) => distanceM >= 1000
      ? `${Number((distanceM / 1000).toFixed(1))} km`
      : `${Math.round(distanceM)} m`;
    ctx.textAlign = 'left';
    ctx.fillText(ringLabel(model.rangeM / 2), centerX + 5, centerY - radius / 2 + 10);
    ctx.fillText(ringLabel(model.rangeM), centerX + 5, centerY - radius + 27);

    const rangeLabel = model.rangeM >= 1000
      ? `${(model.rangeM / 1000).toFixed(1)} km`
      : `${Math.round(model.rangeM)} m`;
    canvas.setAttribute('aria-label', `雷达 Mini Map，探测范围 ${rangeLabel}，目标 ${model.targets.length} 艘`);
  }

  const resizeObserver = typeof ResizeObserver === 'undefined'
    ? null
    : new ResizeObserver(() => draw(lastModel));
  resizeObserver?.observe(canvas);

  return {
    render(model) {
      lastModel = model || buildRadarModel(null, 0);
      draw(lastModel);
    },
    destroy() { resizeObserver?.disconnect(); },
  };
}
