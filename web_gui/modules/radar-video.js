/** Recorded/backend binary spokes only. No generated noise, targets, or clock. */
export async function decodeRadarVideo(document) {
  const [rows, columns] = document?.shape ?? [];
  if (!Number.isInteger(rows) || !Number.isInteger(columns) || rows < 0 || rows > 8192
    || columns < 1 || columns > 4096 || document.encoding !== 'deflate-base64-u8') throw new Error('INVALID_RADAR_ENCODING');
  const compressed = Uint8Array.from(atob(document.data), char => char.charCodeAt(0));
  const reader = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate')).getReader();
  const result = new Uint8Array(rows * columns);
  let offset = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    if (offset + value.length > result.length) { await reader.cancel(); throw new Error('RADAR_LENGTH_MISMATCH'); }
    result.set(value, offset); offset += value.length;
  }
  if (offset !== result.length) throw new Error('RADAR_LENGTH_MISMATCH');
  const hash = await crypto.subtle.digest('SHA-256', result);
  const hex = [...new Uint8Array(hash)].map(v => v.toString(16).padStart(2, '0')).join('');
  if (hex !== document.sha256) throw new Error('RADAR_HASH_MISMATCH');
  return result;
}

export class RadarVideoBuffer {
  constructor() { this.clear(); }
  clear() {
    this.data = null; this.rowTimes = []; this.origins = []; this.bearings = [];
    this.lastEnd = null; this.lastCheckpoint = null; this.status = 'NO_VIDEO';
    this.history = [];
    this.checkpointRequests = new Map();
  }
  async apply(video) {
    if (!video?.chunk || video.status === 'INCOMPLETE') { this.status = video?.status ?? 'NO_VIDEO'; return; }
    let checkpoint = video.checkpoint;
    if (checkpoint?.url) {
      if (!/^\/api\/radar\/checkpoints\/[a-f0-9]{64}$/.test(checkpoint.url)) throw new Error('INVALID_RADAR_CHECKPOINT_URL');
      if (!this.checkpointRequests.has(checkpoint.url)) {
        this.checkpointRequests.set(checkpoint.url, fetch(checkpoint.url).then(response => {
          if (!response.ok) throw new Error('RADAR_CHECKPOINT_UNAVAILABLE');
          return response.json();
        }));
        if (this.checkpointRequests.size > 16) this.checkpointRequests.delete(this.checkpointRequests.keys().next().value);
      }
      checkpoint = await this.checkpointRequests.get(checkpoint.url);
    }
    if (!checkpoint || checkpoint.shape?.[0] !== video.spokes) throw new Error('MISSING_RADAR_CHECKPOINT');
    const checkpointKey = `${checkpoint.sha256}:${checkpoint.t_s}`;
    if (video.spoke_seq_end < this.lastEnd) this.history = [];
    if (checkpointKey !== this.lastCheckpoint || this.lastEnd === null || video.spoke_seq_end < this.lastEnd) {
      if (this.data && video.spoke_seq_end >= this.lastEnd) {
        this.history.push({ data: this.data, rowTimes: this.rowTimes, origins: this.origins, rangeM: this.rangeM, spokes: this.spokes, bins: this.bins });
        this.history = this.history.slice(-2);
      }
      this.data = await decodeRadarVideo(checkpoint);
      this.spokes = checkpoint.shape[0]; this.bins = checkpoint.shape[1];
      this.rowTimes = [...checkpoint.row_times_s]; this.origins = checkpoint.row_origins_ne_m.map(p => [...p]);
      this.bearings = [...checkpoint.row_bearings_rad]; this.lastCheckpoint = checkpointKey;
    }
    const chunk = await decodeRadarVideo(video.chunk);
    if (video.chunk.shape[0] !== video.rows.length || video.chunk.shape[1] !== this.bins) throw new Error('INVALID_RADAR_ROWS');
    for (let i = 0; i < video.rows.length; i++) {
      const row = video.rows[i];
      if (!Number.isInteger(row) || row < 0 || row >= this.spokes) throw new Error('INVALID_RADAR_ROW');
      this.data.set(chunk.subarray(i * this.bins, (i + 1) * this.bins), row * this.bins);
      this.rowTimes[row] = video.row_times_s[i]; this.origins[row] = video.row_origins_ne_m[i];
      this.bearings[row] = video.row_bearings_rad[i];
    }
    this.lastEnd = video.spoke_seq_end; this.rangeM = video.range_m;
    this.status = 'SHADOW';
  }
  raster(size, model, { headingUp = false, courseUp = false, gain = 0, sea = 0, rain = 0, trails = false } = {}) {
    const image = new Uint8ClampedArray(size * size * 4);
    if (!this.data || !model?.hasOwnship) return image;
    const half = size / 2;
    const rotation = headingUp ? model.ownshipHeadingRad : (courseUp ? model.ownshipCourseRad : 0);
    const cos = Math.cos(rotation); const sin = Math.sin(rotation);
    for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
      const localN = (half - y) / half * model.rangeScaleM;
      const localE = (x - half) / half * model.rangeScaleM;
      if (Math.hypot(localN, localE) > model.rangeScaleM) continue;
      const north = localN * cos - localE * sin;
      const east = localN * sin + localE * cos;
      let row = Math.floor((((Math.atan2(east, north) / (2 * Math.PI)) % 1) + 1) % 1 * this.spokes);
      const origin = this.origins[row];
      if (!origin || this.rowTimes[row] < 0) continue;
      // Translate from current ownship to each spoke's acquisition origin.
      let rn = north + model.ownshipNorth - origin[0];
      let re = east + model.ownshipEast - origin[1];
      row = Math.floor((((Math.atan2(re, rn) / (2 * Math.PI)) % 1) + 1) % 1 * this.spokes);
      const corrected = this.origins[row];
      if (!corrected || this.rowTimes[row] < 0) continue;
      rn = north + model.ownshipNorth - corrected[0]; re = east + model.ownshipEast - corrected[1];
      const range = Math.hypot(rn, re);
      const bin = Math.floor(range / this.rangeM * this.bins);
      if (bin < 0 || bin >= this.bins) continue;
      const age = Math.max(0, model.simTimeS - this.rowTimes[row]);
      if (age > model.scanPeriodS * (trails ? 3 : 1.1)) continue;
      const suppression = sea * 0.6 * Math.exp(-range / 1800) + rain * 0.3;
      const value = Math.max(0, Math.min(255, this.data[row * this.bins + bin] + gain * 2 - suppression));
      const persistence = trails ? Math.exp(-age / (model.scanPeriodS * 2)) : 1;
      let trailValue = value * persistence;
      if (trails) for (const past of this.history) {
        const pastOrigin = past.origins[row];
        const pastAge = model.simTimeS - past.rowTimes[row];
        if (!pastOrigin || past.rowTimes[row] < 0 || pastAge < 0 || pastAge > model.scanPeriodS * 3) continue;
        const pr = Math.hypot(north + model.ownshipNorth - pastOrigin[0], east + model.ownshipEast - pastOrigin[1]);
        const pb = Math.floor(pr / past.rangeM * past.bins);
        if (pb >= 0 && pb < past.bins) trailValue = Math.max(trailValue, past.data[row * past.bins + pb] * Math.exp(-pastAge / (model.scanPeriodS * 2)));
      }
      const offset = (y * size + x) * 4;
      image[offset] = trailValue * 0.2; image[offset + 1] = trailValue; image[offset + 2] = trailValue * 0.5;
      image[offset + 3] = 255;
    }
    return image;
  }
}

export function bindRadarControls(panel, radar) {
  if (!panel) return;
  for (const button of panel.querySelectorAll('[data-radar-heading]')) {
    button.addEventListener('click', () => {
      radar.configure({ headingUp: button.dataset.radarHeading === 'heading', courseUp: button.dataset.radarHeading === 'course' });
      for (const other of panel.querySelectorAll('[data-radar-heading]')) {
        other.setAttribute('aria-pressed', String(other === button)); other.classList.toggle('active', other === button);
      }
    });
  }
  for (const button of panel.querySelectorAll('[data-radar-layer]')) {
    button.addEventListener('click', () => {
      const selected = button.getAttribute('aria-pressed') !== 'true';
      button.setAttribute('aria-pressed', String(selected)); button.classList.toggle('active', selected);
      radar.configure({ [button.dataset.radarLayer]: selected });
    });
  }
  for (const slider of panel.querySelectorAll('[data-radar-adjust]')) {
    slider.addEventListener('input', () => radar.configure({ [slider.dataset.radarAdjust]: Number(slider.value) }));
  }
}
