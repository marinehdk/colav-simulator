// Deployment pixel-stream quality. These profiles affect rendering only, never simulation time.
export function chooseTwinStreamProfile(width, height, dpr = 1) {
  if (!(width > 0 && height > 0)) return '1080p';
  const scale = Math.min(width / 16, height / 9) * Math.min(Math.max(dpr || 1, 1), 2);
  return scale * 16 >= 1280 || scale * 9 >= 720 ? '1440p' : '1080p';
}

export function sampleTwinVideoStats(report, previous = null) {
  const rows = report ? Array.from(report.values ? report.values() : report) : [];
  const v = rows.find(r => r.type === 'inbound-rtp' && (r.kind ?? r.mediaType) === 'video');
  if (!v) return null;
  const elapsed = previous?.id === v.id ? (v.timestamp - previous.timestamp) / 1000 : 0;
  const frames = v.framesDecoded - (previous?.framesDecoded ?? v.framesDecoded);
  const bytes = v.bytesReceived - (previous?.bytesReceived ?? v.bytesReceived);
  const dropped = v.framesDropped - (previous?.framesDropped ?? v.framesDropped);
  const valid = elapsed > 0 && frames >= 0 && bytes >= 0;
  const codec = rows.find(r => r.id === v.codecId)?.mimeType ?? null;
  const pair = rows.find(r => r.type === 'candidate-pair' && r.state === 'succeeded' && r.nominated);
  const delta = key => elapsed > 0 && Number.isFinite(v[key]) && Number.isFinite(previous?.[key]) && v[key] >= previous[key] ? v[key] - previous[key] : null;
  const received = delta('packetsReceived'), lost = delta('packetsLost');
  const decode = delta('totalDecodeTime'), buffer = delta('jitterBufferDelay'), emitted = delta('jitterBufferEmittedCount');
  return {
    packetsReceived: v.packetsReceived, packetsLost: v.packetsLost, totalDecodeTime: v.totalDecodeTime,
    jitterBufferDelay: v.jitterBufferDelay, jitterBufferEmittedCount: v.jitterBufferEmittedCount,
    lossRatio: received !== null && lost !== null && received + lost > 0 ? lost / (received + lost) : null,
    decodeMs: decode !== null && frames > 0 ? decode * 1000 / frames : null,
    jitterBufferMs: buffer !== null && emitted > 0 ? buffer * 1000 / emitted : null,
    jitterMs: Number.isFinite(v.jitter) ? v.jitter * 1000 : null,
    freezeCount: v.freezeCount ?? null,
    id: v.id, timestamp: v.timestamp, framesDecoded: v.framesDecoded, bytesReceived: v.bytesReceived,
    framesDropped: v.framesDropped, width: v.frameWidth ?? null, height: v.frameHeight ?? null,
    fps: valid ? frames / elapsed : null,
    bitrateMbps: valid ? bytes * 8 / elapsed / 1e6 : null,
    dropRatio: valid && dropped >= 0 && frames + dropped > 0 ? dropped / (frames + dropped) : null,
    rttMs: Number.isFinite(pair?.currentRoundTripTime) ? pair.currentRoundTripTime * 1000 : null,
    codec,
  };
}
