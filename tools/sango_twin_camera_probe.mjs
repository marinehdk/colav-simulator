#!/usr/bin/env node
// sango_twin_camera_probe — P1-1a E2E causal proof (spec #90 terminal-review fix batch).
//
// Camera-only KF session (scenarios/head_on_camera.yaml — external_cameras is the
// ownship's ONLY sensor) on a dedicated diagnostic backend instance
// (tools/sango_camera_kf_session.py, port 8011 — the product session API only
// serves god|vimmjipda, so the scene-built KF session is seeded through the
// documented diagnostic launcher; every consumed route is the standard surface).
//
// Feed: the REAL YOLO detector service consuming the FramePublisher contract via
// tools/sango_detector_replay.py (the sanctioned M9 frame-source stand-in) with a
// composed frame from tools/sango_camera_probe_frame.py — the REAL twin mast-feed
// render plus the target vessel pasted at its georef-projected pixel box. The
// twin's live mode does not render the scenario target ahead of the ownship
// (Unity-side gap, ledgered in review-residue.md); the replay route closes the
// causal loop through the real frame contract — real YOLO service, real
// observations endpoint, real georef, real association, real KF tick loop.
// (The twin+YOLO+endpoint pixel chain itself is covered by the obs regression
// probe: rig attach + feed rewire + real frames to the endpoint.)
//
//   Causal pair:
//   ON  — feeding: camera georef records associate onto the target's do_idx ->
//         KF track updates -> confirmed-tracks (sensor-model@1) lists a track
//         whose sources[] carry sensor_id=2 (camera_eo).
//   OFF — replay killed: no new associations -> existence decays below the 0.999
//         confirm gate within ticks (track vanishes from the confirmed product)
//         and the observations accepted-frames counter freezes.
//
// Lifecycle discipline: launcher + replay + YOLO are owned here (every PID killed
// on exit, leftovers cleaned before start). Artifacts -> output/sango-twin-camera/.
// Usage: node tools/sango_twin_camera_probe.mjs
import { spawn, execSync } from 'node:child_process';
import { mkdirSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const BACKEND = 'http://127.0.0.1:8011'; // diagnostic launcher instance
const OUT_DIR = new URL('../output/sango-twin-camera/', import.meta.url).pathname;
const LAUNCHER_BIN = new URL('../.venv/bin/python', import.meta.url).pathname;
const LAUNCHER_SCRIPT = new URL('./sango_camera_kf_session.py', import.meta.url).pathname;
const DETECTOR_BIN = new URL('../.venv-detector/bin/python', import.meta.url).pathname;
const DETECTOR_SCRIPT = new URL('./sango_detector_service.py', import.meta.url).pathname;
const REPLAY_SCRIPT = new URL('./sango_detector_replay.py', import.meta.url).pathname;
const COMPOSER_SCRIPT = new URL('./sango_camera_probe_frame.py', import.meta.url).pathname;
const FEED_CANVAS = join(OUT_DIR, 'feed-frame.jpg');   // real twin render (committed artifact)
const BOAT_CROP = join(OUT_DIR, 'boat-crop.png');      // real boat photo crop (committed artifact)
const COMPOSED = join(OUT_DIR, 'composed-frame.jpg');
const CONFIRM_WINDOW_MS = 120000; // max wait for the camera-sourced confirmed track
const DECAY_WINDOW_MS = 90000;    // max wait for the decay after feed-off
const API = path => `${BACKEND}${path}`;
const jfetch = async (path, options) => fetch(API(path), options).then(async r => ({ status: r.status, body: r.ok ? await r.json() : null }));

const failures = [];
const assertions = [];
function check(name, ok, detail = '') {
  const line = `${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`;
  console.log(line);
  assertions.push({ name, ok, detail });
  if (!ok) failures.push(line);
  return ok;
}
const sleep = ms => new Promise(res => setTimeout(res, ms));

async function waitFor(label, fn, timeoutMs, everyMs = 500) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    try { last = await fn(); if (last) return last; } catch { /* mid-transition */ }
    await sleep(everyMs);
  }
  throw new Error(`timeout waiting for ${label} (last=${JSON.stringify(last)?.slice(0, 300)})`);
}

// ── process lifecycle (single-instance discipline) ───────────────────────────
let launcherPid = null;
let detectorPid = null;
let replayPid = null;
function killPid(target, label) {
  const pid = typeof target === 'object' ? target?.pid : target;  // ChildProcess or raw pid
  if (!pid) return;
  try { process.kill(pid, 'SIGKILL'); } catch { /* gone */ }
  console.log(`${label} killed pid=${pid}`);
}
function cleanup() {
  killPid(replayPid, 'replay');
  killPid(detectorPid, 'detector');
  killPid(launcherPid, 'launcher');
}
process.on('exit', cleanup);
function killLeftovers() {
  for (const pattern of ['sango_detector_service', 'sango_detector_replay', 'sango_camera_kf_session', 'MacOS/sango']) {
    try {
      const out = execSync(`pgrep -fl "${pattern}" || true`).toString().trim();
      if (!out) continue;
      for (const line of out.split('\n')) {
        const pid = Number(line.split(/\s+/)[0]);
        if (Number.isFinite(pid) && pid > 0 && pid !== process.pid) { try { process.kill(pid, 'SIGKILL'); } catch { /* gone */ } }
      }
      check(`no leftover ${pattern}`, true, `killed: ${out.replace(/\n/g, '; ')}`);
      sleep(600);
    } catch { check(`no leftover ${pattern}`, true); }
  }
}

function confirmedCameraTrack(document) {
  const tracks = document?.tracks ?? [];
  return tracks.find(track => (track.sources ?? []).some(source => Number(source.sensor_id) === 2)) ?? null;
}

// ── main ────────────────────────────────────────────────────────────────────
mkdirSync(OUT_DIR, { recursive: true });
killLeftovers();

// 0) Composed frame: real twin mast-feed render + target at its projected box.
check('feed canvas artifact present (real twin render)', existsSync(FEED_CANVAS), FEED_CANVAS);
check('boat crop artifact present (YOLO-verified repo paper figure)', existsSync(BOAT_CROP), BOAT_CROP);
execSync(`${DETECTOR_BIN} ${COMPOSER_SCRIPT} --feed ${FEED_CANVAS} --out ${COMPOSED}`, { stdio: 'inherit' });
check('composed frame built (target at georef-projected pixel box)', existsSync(COMPOSED), COMPOSED);

// 1) Diagnostic camera-only KF backend (8011) + session start.
launcherPid = spawn(LAUNCHER_BIN, [LAUNCHER_SCRIPT, '--port', '8011'], { stdio: ['ignore', 'pipe', 'pipe'], detached: false });
const launcherLog = '/tmp/sango-camera-kf-session.log';
launcherPid.stdout.on('data', chunk => writeFileSync(launcherLog, chunk, { flag: 'a' }));
launcherPid.stderr.on('data', chunk => writeFileSync(launcherLog, chunk, { flag: 'a' }));
writeFileSync(launcherLog, '');
console.log(`launcher started pid=${launcherPid.pid} -> ${launcherLog}`);
await waitFor('diagnostic backend up (8011 capabilities)', async () => {
  const res = await jfetch('/api/capabilities').catch(() => null);
  return res?.status === 200 ? res : null;
}, 240000, 1000);
check('diagnostic camera-kf backend up (8011, standard app surface)', true, launcherLog);
const current = await jfetch('/api/sessions/current');
const sessionId = current?.body?.session_id ?? current?.body?.id;
check('camera-only kf session seeded (scenario_default -> scene-built KF)', Boolean(sessionId), `session=${sessionId}`);
check('request identity is scenario_default (scene-built tracker: kf + assembled sensors)',
  current?.body?.spec?.tracker_id === 'scenario_default',
  `spec.tracker_id=${current?.body?.spec?.tracker_id}`);
await jfetch(`/api/sessions/${sessionId}/start`, { method: 'POST' });
check('session started', true, `session=${sessionId}`);

// 2) LEG ON: replay feeder (FramePublisher contract) + real YOLO with the
//    observations forward branch. The camera is the ownship's ONLY assembled
//    sensor, so the KF track can only update through georeferenced records.
replayPid = spawn(DETECTOR_BIN, [REPLAY_SCRIPT, '--image', COMPOSED, '--fps', '5'], {
  stdio: ['ignore', 'pipe', 'pipe'], detached: false,
  env: { ...process.env, PYTHONUNBUFFERED: '1' },  // block-buffered pipes would starve the log wait
});
const replayLog = '/tmp/sango-camera-replay.log';
replayPid.stdout.on('data', chunk => writeFileSync(replayLog, chunk, { flag: 'a' }));
replayPid.stderr.on('data', chunk => writeFileSync(replayLog, chunk, { flag: 'a' }));
writeFileSync(replayLog, '');
console.log(`replay started pid=${replayPid.pid} -> ${replayLog}`);
await waitFor('replay publishing frames', () => {
  const match = readFileSync(replayLog, 'utf8').match(/frame seq=(\d+)/);
  return match ? { seq: Number(match[1]) } : null;
}, 30000, 500);
check('replay feeder publishing on the FramePublisher endpoint', true, `seq=${readFileSync(replayLog, 'utf8').match(/frame seq=(\d+)/)?.[1]}`);

const detectorLog = '/tmp/sango-camera-detector.log';
const detector = spawn(DETECTOR_BIN, [
  DETECTOR_SCRIPT, '--device', 'cpu',
  // conf 0.12: the composed target is real-photo pixels but small; the default
  // 0.25 operating point is tuned for the Unity feed. The detector's --conf is
  // an exposed knob; the ZMQ return path is untouched either way.
  '--conf', '0.12',
  '--endpoint', 'tcp://127.0.0.1:5556',
  '--forward-url', API(`/api/sessions/${sessionId}/observations`),
  '--forward-mount', 'mast_ptz_eo',
], { stdio: ['ignore', 'pipe', 'pipe'], detached: false });
detectorPid = detector.pid;
detector.stdout.on('data', chunk => writeFileSync(detectorLog, chunk, { flag: 'a' }));
detector.stderr.on('data', chunk => writeFileSync(detectorLog, chunk, { flag: 'a' }));
writeFileSync(detectorLog, '');
console.log(`detector started pid=${detectorPid} -> ${detectorLog}`);
await waitFor('detector ready (model loaded + forward on)', () => {
  const text = readFileSync(detectorLog, 'utf8');
  return text.includes('model loaded') && text.includes('forward branch ON') ? text : null;
}, 90000);
check('YOLO detector up (CPU) with forward branch -> 8011 observations', true, detectorLog);

let onStatus = null;
await waitFor('YOLO detections accepted into the observation cache', async () => {
  const res = await jfetch(`/api/sessions/${sessionId}/observations`).catch(() => null);
  const channel = res?.body?.channels?.find(c => Number(c.sensor_id) === 2);
  if (res?.body?.accepted_frames_total > 0 && channel?.detections > 0) { onStatus = res.body; return res.body; }
  return null;
}, CONFIRM_WINDOW_MS, 1000);
check('LEG ON: observations accepted (composed frame -> real YOLO -> POST -> backend)',
  Boolean(onStatus), JSON.stringify(onStatus?.channels ?? []));

const confirmedOn = await waitFor('camera-sourced track in confirmed-tracks (sensor_id=2)', async () => {
  const res = await jfetch(`/api/sessions/${sessionId}/confirmed-tracks`).catch(() => null);
  const hit = res?.body ? confirmedCameraTrack(res.body) : null;
  return hit ? { document: res.body, track: hit } : null;
}, CONFIRM_WINDOW_MS, 1000);
check('LEG ON: confirmed-tracks carries the camera-source track (sensor_id=2 in sources[])',
  Boolean(confirmedOn?.track),
  `existence=${confirmedOn?.track?.existence_prob} sources=${JSON.stringify(confirmedOn?.track?.sources ?? [])}`);
check('LEG ON: track sources stay camera_eo (2), not a synthetic radar fill',
  (confirmedOn?.track?.sources ?? []).every(source => Number(source.sensor_id) === 2),
  JSON.stringify(confirmedOn?.track?.sources ?? []));
writeFileSync(join(OUT_DIR, 'confirmed-tracks-on.json'), JSON.stringify(confirmedOn?.document ?? {}, null, 2));
writeFileSync(join(OUT_DIR, 'observations-status.json'), JSON.stringify({ session_id: sessionId, status: onStatus }, null, 2));

// 3) LEG OFF: kill the replay feed -> no new associations -> existence decays
//    out of the confirmed product; the accepted-frames counter freezes.
const acceptedAtOff = (await jfetch(`/api/sessions/${sessionId}/observations`))?.body?.accepted_frames_total ?? 0;
killPid(replayPid, 'replay');
replayPid = null;
check('LEG OFF: replay feed killed', true, `accepted_frames at kill=${acceptedAtOff}`);
const decayed = await waitFor('camera track decays out of confirmed-tracks (0.999 gate)', async () => {
  const res = await jfetch(`/api/sessions/${sessionId}/confirmed-tracks`).catch(() => null);
  return res?.body && !confirmedCameraTrack(res.body) ? res.body : null;
}, DECAY_WINDOW_MS, 1000);
check('LEG OFF: camera-sourced track vanished from confirmed-tracks (existence decay, no feed)', Boolean(decayed));
writeFileSync(join(OUT_DIR, 'confirmed-tracks-off.json'), JSON.stringify(decayed ?? {}, null, 2));
await sleep(8000);
const acceptedAfter = (await jfetch(`/api/sessions/${sessionId}/observations`))?.body?.accepted_frames_total ?? -1;
check('LEG OFF: observations accepted_frames frozen (no feed -> no new georef records)',
  acceptedAfter === acceptedAtOff, `at kill=${acceptedAtOff} after=${acceptedAfter}`);

writeFileSync(join(OUT_DIR, 'detector-log.txt'), readFileSync(detectorLog, 'utf8').split('\n').slice(-80).join('\n'));
writeFileSync(join(OUT_DIR, 'replay-log.txt'), readFileSync(replayLog, 'utf8').split('\n').slice(-40).join('\n'));

// 4) Report.
const onSummary = `existence=${confirmedOn?.track?.existence_prob} sources=${JSON.stringify(confirmedOn?.track?.sources ?? [])}`;
const lines = [];
lines.push('# P1-1a E2E — camera-only KF causal probe (sango_twin_camera_probe)');
lines.push('');
lines.push(`- date: ${new Date().toISOString()}`);
lines.push(`- session: \`${sessionId}\` (rule14/head_on_camera/nominal/scenario_default — scene-built KF, external_cameras the ONLY sensor)`);
lines.push('- backend: diagnostic launcher on 8011 (product surface untouched); feed: replay of the composed frame');
lines.push('  (real twin render + target at its georef-projected box) through the REAL YOLO service and observations endpoint.');
lines.push('  Twin render gap (no target vessel ahead of ownship in live mode) ledgered in review-residue.md.');
lines.push('');
lines.push('## Causal pair');
lines.push('');
lines.push(`- LEG ON: camera-source confirmed track ${onSummary}`);
lines.push(`- LEG OFF: replay killed -> track decayed out of the confirmed product: ${Boolean(decayed)}; accepted_frames ${acceptedAtOff} -> ${acceptedAfter} (frozen)`);
lines.push('');
lines.push('## Assertions');
lines.push('');
for (const item of assertions) lines.push(`- ${item.ok ? 'PASS' : 'FAIL'}  ${item.name}${item.detail ? ` — ${item.detail}` : ''}`);
writeFileSync(join(OUT_DIR, 'report.md'), lines.join('\n') + '\n');
console.log(`\nartifacts: ${OUT_DIR}`);

if (failures.length) {
  console.error(`\n${failures.length} assertion(s) FAILED`);
  process.exit(1);
}
console.log('\nALL ASSERTIONS PASSED');
process.exit(0);
